import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.templating import templates

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class AuthError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class LoginRequired(Exception):
    pass


MESSAGES = {
    "missing": "Обязательное поле",
    "string_too_short": "Минимальная длина: {min_length}",
    "string_too_long": "Максимальная длина: {max_length}",
    "string_pattern_mismatch": "Неверный формат",
    "greater_than": "Значение должно быть больше {gt}",
    "greater_than_equal": "Значение должно быть не меньше {ge}",
    "int_parsing": "Нужно целое число",
    "int_type": "Нужно целое число",
    "decimal_parsing": "Нужно число",
    "decimal_type": "Нужно число",
    "decimal_max_places": "Слишком много знаков после запятой (максимум {decimal_places})",
    "decimal_whole_digits": "Слишком большое число",
    "date_parsing": "Неверная дата, нужен формат ГГГГ-ММ-ДД",
    "date_from_datetime_parsing": "Неверная дата, нужен формат ГГГГ-ММ-ДД",
    "literal_error": "Недопустимое значение",
    "json_invalid": "Некорректный JSON",
}

HTTP_MESSAGES = {
    404: "Не найдено",
    405: "Метод не поддерживается",
}


def error_message(error: dict) -> str:
    kind = error["type"]
    ctx = error.get("ctx", {})
    if kind == "string_too_short" and ctx.get("min_length") == 1:
        return "Поле не может быть пустым"
    if kind == "value_error":
        return str(ctx.get("error", error["msg"]))
    template = MESSAGES.get(kind)
    return template.format(**ctx) if template else error["msg"]


def field_errors(errors) -> dict[str, str]:
    result = {}
    for error in errors:
        field = str(error["loc"][-1]) if error["loc"] else "__all__"
        result.setdefault(field, error_message(error))
    return result


def error_response(request: Request, status_code: int, message: str):
    if request.url.path.startswith("/api") or request.url.path == "/health":
        content = {"detail": message}
        if status_code >= 500:
            content["request_id"] = getattr(request.state, "request_id", None)
        return JSONResponse(status_code=status_code, content=content)
    context = {"status_code": status_code, "message": message, "user": None}
    return templates.TemplateResponse(request, "error.html", context, status_code=status_code)


def register_error_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(request, exc.status_code, exc.message)

    @app.exception_handler(LoginRequired)
    async def login_required_handler(request: Request, exc: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(part) for part in e["loc"][1:]) or str(e["loc"][0]),
                "message": error_message(e),
            }
            for e in exc.errors()
        ]
        if not request.url.path.startswith("/api"):
            return error_response(request, 422, "Некорректный запрос")
        return JSONResponse(
            status_code=422,
            content={"detail": "Некорректные данные запроса", "errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        message = HTTP_MESSAGES.get(exc.status_code, str(exc.detail))
        return error_response(request, exc.status_code, message)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning("нарушение целостности БД: %s", exc.orig)
        return error_response(
            request, 409, "Операция нарушает целостность данных (дубликат или связанная запись)"
        )
