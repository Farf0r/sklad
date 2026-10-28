import logging
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import CurrentUser, DbSession
from app.errors import AuthError
from app.schemas.auth import LoginIn, UserOut
from app.services.users import authenticate
from app.templating import templates

logger = logging.getLogger(__name__)

api = APIRouter(prefix="/api/auth", tags=["Авторизация"])
pages = APIRouter(include_in_schema=False)


def start_session(request: Request, user_id: int):
    request.session.clear()
    request.session["user_id"] = user_id


@api.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, db: DbSession):
    user = authenticate(db, data.username, data.password)
    if user is None:
        logger.warning("неудачная попытка входа: %s", data.username)
        raise AuthError("Неверный логин или пароль")
    start_session(request, user.id)
    logger.info("вход в систему: %s", user.username)
    return user


@api.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@api.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@pages.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"user": None, "username": ""})


@pages.post("/login")
def login_submit(  # nosec B107 — пустая строка по умолчанию у поля формы, а не пароль в коде
    request: Request,
    db: DbSession,
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
):
    user = authenticate(db, username, password)
    if user is None:
        logger.warning("неудачная попытка входа: %s", username)
        context = {"user": None, "username": username, "error": "Неверный логин или пароль"}
        return templates.TemplateResponse(request, "login.html", context, status_code=401)
    start_session(request, user.id)
    logger.info("вход в систему: %s", user.username)
    return RedirectResponse("/", status_code=303)


@pages.post("/logout")
def logout_submit(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
