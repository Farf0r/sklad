from pydantic import BaseModel, ValidationError

from app.errors import field_errors


def validate_form(schema: type[BaseModel], form: dict):
    """Возвращает (данные, {}) или (None, {поле: текст ошибки})."""
    try:
        return schema.model_validate(form), {}
    except ValidationError as exc:
        return None, field_errors(exc.errors())
