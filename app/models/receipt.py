from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.material import Material
from app.models.supplier import Supplier
from app.models.user import User


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (CheckConstraint("status in ('draft', 'posted')", name="ck_receipts_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    receipt_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    comment: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    created_by: Mapped[User] = relationship(lazy="joined")
    items: Mapped[list["ReceiptItem"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptItem.id",
        lazy="selectin",
    )

    @property
    def total(self) -> Decimal:
        return sum((item.amount for item in self.items), Decimal("0.00"))


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    __table_args__ = (
        UniqueConstraint("receipt_id", "material_id", name="uq_receipt_items_material"),
        CheckConstraint("quantity > 0", name="ck_receipt_items_quantity"),
        CheckConstraint("price >= 0", name="ck_receipt_items_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    receipt: Mapped[Receipt] = relationship(back_populates="items")
    material: Mapped[Material] = relationship(lazy="joined")

    @property
    def amount(self) -> Decimal:
        return (self.quantity * self.price).quantize(Decimal("0.01"))
