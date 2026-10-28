from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.unit import Unit


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_materials_stock"),
        CheckConstraint("min_stock >= 0", name="ck_materials_min_stock"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, server_default="0")
    # минимальный остаток: если остаток меньше, материал пора заказать; 0 — не отслеживать
    min_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, server_default="0")
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    unit: Mapped[Unit] = relationship(lazy="joined")

    @property
    def needs_order(self) -> bool:
        return self.stock < self.min_stock

    @property
    def shortage(self) -> Decimal:
        """Сколько не хватает до минимального остатка."""
        return max(self.min_stock - self.stock, Decimal("0"))
