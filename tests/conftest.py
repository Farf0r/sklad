import os
import tempfile

# Тесты не трогают рабочую БД из .env: по умолчанию используется временная SQLite-база,
# а через TEST_DATABASE_URL можно указать отдельную тестовую базу PostgreSQL
TEST_DB = os.path.join(tempfile.gettempdir(), "sklad_test.db")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TEST_DB}")
os.environ["SECRET_KEY"] = "test-secret-key-only-for-pytest"
os.environ["APP_ENV"] = "test"
os.environ["LOG_FILE"] = ""
os.environ["BCRYPT_ROUNDS"] = "4"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.users import create_user  # noqa: E402

PASSWORD = "password123"


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


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
