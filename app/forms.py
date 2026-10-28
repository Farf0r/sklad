from pydantic import BaseModel, ValidationError

from app.errors import field_errors


def decimal_input(value: str) -> str:
    # в русской раскладке дробную часть часто пишут через запятую
    return value.strip().replace(",", ".").replace(" ", "")


def validate_form(schema: type[BaseModel], form: dict):
    """Возвращает (данные, {}) или (None, {поле: текст ошибки})."""
    try:
        return schema.model_validate(form), {}
    except ValidationError as exc:
        return None, field_errors(exc.errors())
