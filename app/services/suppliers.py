import logging

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierIn

logger = logging.getLogger(__name__)


def list_suppliers(db: Session) -> list[Supplier]:
    return list(db.scalars(select(Supplier).order_by(Supplier.name)))


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError(f"Поставщик {supplier_id} не найден")
    return supplier


def check_unique(db: Session, data: SupplierIn, exclude_id: int | None = None):
    query = select(Supplier).where(or_(Supplier.name == data.name, Supplier.inn == data.inn))
    if exclude_id is not None:
        query = query.where(Supplier.id != exclude_id)
    if db.scalar(query.limit(1)):
        raise ConflictError("Поставщик с таким названием или ИНН уже есть")


def create_supplier(db: Session, data: SupplierIn) -> Supplier:
    check_unique(db, data)
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    db.commit()
    logger.info("добавлен поставщик %s (id=%s)", supplier.name, supplier.id)
    return supplier


def update_supplier(db: Session, supplier_id: int, data: SupplierIn) -> Supplier:
    supplier = get_supplier(db, supplier_id)
    check_unique(db, data, exclude_id=supplier_id)
    for field, value in data.model_dump().items():
        setattr(supplier, field, value)
    db.commit()
    logger.info("изменён поставщик id=%s", supplier_id)
    return supplier


def delete_supplier(db: Session, supplier_id: int):
    supplier = get_supplier(db, supplier_id)
    db.delete(supplier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Нельзя удалить: от поставщика уже есть поступления") from None
    logger.info("удалён поставщик id=%s", supplier_id)
