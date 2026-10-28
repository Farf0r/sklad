import pytest

from app.database import SessionLocal
from app.errors import AppError, ConflictError
from app.services.users import create_user
from tests.conftest import PASSWORD


def test_login_and_me(user_client):
    response = user_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "ivanov"
    assert response.json()["role"] == "storekeeper"


def test_me_without_login_returns_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_wrong_password(client):
    with SessionLocal() as db:
        create_user(db, "petrov", PASSWORD)
    response = client.post("/api/auth/login", json={"username": "petrov", "password": "wrong-pass"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"


def test_login_validation_error(client):
    response = client.post("/api/auth/login", json={"username": ""})
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"username", "password"}


def test_logout(user_client):
    assert user_client.post("/api/auth/logout").status_code == 204
    assert user_client.get("/api/auth/me").status_code == 401


def test_password_is_not_stored_in_plain_text():
    with SessionLocal() as db:
        user = create_user(db, "sidorov", PASSWORD)
    assert user.password_hash != PASSWORD


def test_duplicate_user():
    with SessionLocal() as db:
        create_user(db, "sidorov", PASSWORD)
        with pytest.raises(ConflictError):
            create_user(db, "sidorov", PASSWORD)


def test_short_password_rejected():
    with SessionLocal() as db, pytest.raises(AppError):
        create_user(db, "short", "123")


def test_web_pages_require_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_web_login_form(client):
    with SessionLocal() as db:
        create_user(db, "petrov", PASSWORD)
    response = client.post(
        "/login", data={"username": "petrov", "password": PASSWORD}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "petrov" in client.get("/").text
