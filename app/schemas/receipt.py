from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReceiptItemIn(BaseModel):
    material_id: int = Field(gt=0)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3, examples=["10.5"])
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2, examples=["450.00"])


class ReceiptIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_id: int = Field(gt=0)
    receipt_date: date = Field(default_factory=date.today)
    comment: str | None = Field(default=None, max_length=500)
    items: list[ReceiptItemIn] = Field(default_factory=list)


class RefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class ReceiptItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material: RefOut
    quantity: Decimal
    price: Decimal
    amount: Decimal


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier: RefOut
    receipt_date: date
    status: str
    comment: str | None
    created_by: UserRefOut
    created_at: datetime
    posted_at: datetime | None
    items: list[ReceiptItemOut]
    total: Decimal
