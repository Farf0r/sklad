import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.material import Material
from app.models.receipt import Receipt, ReceiptItem
from app.models.user import User
from app.schemas.receipt import ReceiptIn, ReceiptItemIn
from app.services.materials import get_material
from app.services.suppliers import get_supplier

logger = logging.getLogger(__name__)


def list_receipts(db: Session, status: str | None = None) -> list[Receipt]:
    query = select(Receipt).order_by(Receipt.receipt_date.desc(), Receipt.id.desc())
    if status:
        query = query.where(Receipt.status == status)
    return list(db.scalars(query))


def get_receipt(db: Session, receipt_id: int, for_update: bool = False) -> Receipt:
    query = select(Receipt).where(Receipt.id == receipt_id)
    if for_update:
        # блокируем строку, чтобы одно поступление нельзя было провести дважды одновременно
        query = query.with_for_update(of=Receipt).execution_options(populate_existing=True)
    receipt = db.scalar(query)
    if receipt is None:
        raise NotFoundError(f"Поступление {receipt_id} не найдено")
    return receipt


def ensure_draft(receipt: Receipt):
    if receipt.status != "draft":
        raise ConflictError("Поступление уже проведено, изменять или удалять его нельзя")


def check_new_item(db: Session, receipt: Receipt, data: ReceiptItemIn):
    get_material(db, data.material_id)
    if any(item.material_id == data.material_id for item in receipt.items):
        raise ConflictError("Этот материал уже есть в поступлении")


def create_receipt(db: Session, data: ReceiptIn, user: User) -> Receipt:
    get_supplier(db, data.supplier_id)
    receipt = Receipt(
        supplier_id=data.supplier_id,
        receipt_date=data.receipt_date,
        comment=data.comment or None,
        created_by_id=user.id,
    )
    for item in data.items:
        check_new_item(db, receipt, item)
        receipt.items.append(ReceiptItem(**item.model_dump()))
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    logger.info("создано поступление id=%s, строк: %s", receipt.id, len(receipt.items))
    return receipt


def add_item(db: Session, receipt_id: int, data: ReceiptItemIn) -> Receipt:
    receipt = get_receipt(db, receipt_id, for_update=True)
    ensure_draft(receipt)
    check_new_item(db, receipt, data)
    receipt.items.append(ReceiptItem(**data.model_dump()))
    db.commit()
    db.refresh(receipt)
    return receipt


def remove_item(db: Session, receipt_id: int, item_id: int) -> Receipt:
    receipt = get_receipt(db, receipt_id, for_update=True)
    ensure_draft(receipt)
    item = next((item for item in receipt.items if item.id == item_id), None)
    if item is None:
        raise NotFoundError(f"Строка {item_id} в поступлении {receipt_id} не найдена")
    receipt.items.remove(item)
    db.commit()
    db.refresh(receipt)
    return receipt


def delete_receipt(db: Session, receipt_id: int):
    receipt = get_receipt(db, receipt_id, for_update=True)
    ensure_draft(receipt)
    db.delete(receipt)
    db.commit()
    logger.info("удалено поступление id=%s", receipt_id)


def post_receipt(db: Session, receipt_id: int) -> Receipt:
    """Проводит поступление: увеличивает остатки материалов и закрывает документ для изменений."""
    receipt = get_receipt(db, receipt_id, for_update=True)
    ensure_draft(receipt)
    if not receipt.items:
        raise ConflictError("Нельзя провести поступление без строк")

    for item in receipt.items:
        db.execute(
            update(Material)
            .where(Material.id == item.material_id)
            .values(stock=Material.stock + item.quantity)
        )
    receipt.status = "posted"
    receipt.posted_at = datetime.now(UTC)
    db.commit()
    db.refresh(receipt)
    logger.info(
        "проведено поступление id=%s: строк %s, сумма %s",
        receipt.id,
        len(receipt.items),
        receipt.total,
    )
    return receipt
