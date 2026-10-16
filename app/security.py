from typing import Annotated

import bcrypt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.errors import AuthError, ForbiddenError, LoginRequired
from app.models.user import User

# bcrypt не принимает пароли длиннее 72 байт
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode()
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(raw, password_hash.encode())


def session_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get(User, user_id)


def current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    user = session_user(request, db)
    if user is None:
        raise AuthError("Требуется вход в систему")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "admin":
        raise ForbiddenError("Действие доступно только администратору")
    return user


def web_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    user = session_user(request, db)
    if user is None:
        raise LoginRequired()
    return user
