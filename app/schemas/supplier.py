from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200, examples=["ООО «СтройБаза»"])
    inn: str = Field(examples=["7701234567"])
    phone: str | None = Field(default=None, max_length=30, examples=["+7 495 123-45-67"])
    email: str | None = Field(default=None, max_length=100, examples=["info@stroybaza.ru"])
    address: str | None = Field(default=None, max_length=300)

    @field_validator("inn")
    @classmethod
    def check_inn(cls, value: str) -> str:
        if not value.isdigit() or len(value) not in (10, 12):
            raise ValueError("ИНН должен состоять из 10 или 12 цифр")
        return value

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str | None) -> str | None:
        if value and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise ValueError("Некорректный адрес электронной почты")
        return value or None

    @field_validator("phone", "address")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        return value or None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    inn: str
    phone: str | None
    email: str | None
    address: str | None
