"""Общая подготовка тестов.

Тесты работают только с отдельной тестовой базой PostgreSQL из TEST_DATABASE_URL
(переменная окружения или файл .env.test). Перед первым тестом, которому нужна база,
схема создаётся миграциями, перед каждым таким тестом все таблицы очищаются, поэтому
тесты не зависят друг от друга. Unit-тесты (tests/unit) к базе не обращаются.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent


def read_test_database_url() -> str | None:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env_file = ROOT / ".env.test"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.strip().partition("=")
            if key == "TEST_DATABASE_URL" and value:
                return value
    return None


TEST_DATABASE_URL = read_test_database_url()
if not TEST_DATABASE_URL:
    pytest.exit(
        "Не задана тестовая база. Создайте базу sklad_test и файл .env.test по образцу "
        ".env.test.example (см. README, раздел «Тесты»)",
        returncode=2,
    )
url = make_url(TEST_DATABASE_URL)
if not url.drivername.startswith("postgresql") or not (url.database or "").endswith("_test"):
    pytest.exit(
        "TEST_DATABASE_URL должна указывать на базу PostgreSQL с именем *_test: "
        "тесты удаляют в ней все данные",
        returncode=2,
    )

# настройки приложения подменяются до его импорта: рабочая база из .env не используется
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test-secret-key-only-for-pytest"
os.environ["APP_ENV"] = "test"
os.environ["LOG_FILE"] = ""
os.environ["BCRYPT_ROUNDS"] = "4"

from fastapi.testclient import TestClient  # noqa: E402 — после подмены настроек
from sqlalchemy import MetaData, text  # noqa: E402 — после подмены настроек

from app.database import Base, SessionLocal, engine  # noqa: E402 — после подмены настроек
from app.main import app  # noqa: E402 — после подмены настроек
from app.migrate import migrate  # noqa: E402 — после подмены настроек
from app.services.users import create_user  # noqa: E402 — после подмены настроек

PASSWORD = "password123"
TABLES = ", ".join(table.name for table in Base.metadata.sorted_tables)


def drop_everything():
    metadata = MetaData()
    metadata.reflect(bind=engine)
    metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def database_schema():
    drop_everything()
    migrate()


@pytest.fixture(autouse=True)
def clean_tables(request):
    # unit-тестам база не нужна: они проходят, даже если PostgreSQL недоступен
    if "unit" in request.node.path.parts:
        return
    request.getfixturevalue("database_schema")
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client():
    return TestClient(app)


def logged_in_client(username: str, role: str) -> TestClient:
    with SessionLocal() as db:
        create_user(db, username, PASSWORD, role)
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return client


@pytest.fixture
def admin_client():
    return logged_in_client("admin", "admin")


@pytest.fixture
def user_client():
    return logged_in_client("ivanov", "storekeeper")
