"""Ошибки сервера и недоступная база: приложение отвечает понятно и не падает."""

import logging

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.services import units


def test_unexpected_error_returns_500_with_request_id(user_client, monkeypatch):
    def broken(db):
        raise RuntimeError("что-то сломалось")

    monkeypatch.setattr(units, "list_units", broken)
    response = user_client.get("/api/units", headers={"X-Request-ID": "test-id-123"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Внутренняя ошибка сервера", "request_id": "test-id-123"}
    assert response.headers["X-Request-ID"] == "test-id-123"


def test_unexpected_error_on_page_shows_error_page(user_client, monkeypatch):
    monkeypatch.setattr(units, "list_units", lambda db: 1 / 0)
    response = user_client.get("/units")
    assert response.status_code == 500
    assert "text/html" in response.headers["content-type"]


class BrokenSession:
    def execute(self, *args, **kwargs):
        raise ConnectionError("база недоступна")


def test_health_when_database_is_down(client):
    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["db"] == "unavailable"


def test_unknown_page_returns_html_404(user_client):
    response = user_client.get("/no-such-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]


def test_wrong_password_on_login_page(client):
    response = client.post("/login", data={"username": "nobody", "password": "wrong-pass"})
    assert response.status_code == 401
    assert "Неверный логин или пароль" in response.text


def test_startup_and_shutdown_are_logged(caplog):
    with caplog.at_level(logging.INFO), TestClient(app):
        pass
    assert "запущен" in caplog.text
    assert "остановлен" in caplog.text
