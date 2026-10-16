from pydantic import BaseModel, ConfigDict, Field


class UnitIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=50, examples=["Килограмм"])
    short_name: str = Field(min_length=1, max_length=10, examples=["кг"])


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str
