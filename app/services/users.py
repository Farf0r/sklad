import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, ConflictError
from app.models.user import ROLES, User
from app.security import MAX_PASSWORD_BYTES, hash_password, verify_password

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, username: str, password: str, role: str = "storekeeper") -> User:
    username = username.strip()
    if not username:
        raise AppError("Логин не может быть пустым")
    if role not in ROLES:
        raise AppError(f"Неизвестная роль: {role}")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AppError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise AppError("Пароль слишком длинный")
    if db.scalar(select(User).where(User.username == username)):
        raise ConflictError(f"Пользователь {username} уже существует")

    user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    logger.info("создан пользователь %s с ролью %s", username, role)
    return user
