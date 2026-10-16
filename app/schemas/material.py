from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.unit import UnitOut


class MaterialIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200, examples=["Цемент М500"])
    unit_id: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=500)


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: UnitOut
    stock: Decimal
    description: str | None
