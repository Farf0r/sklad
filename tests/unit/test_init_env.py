"""Создание .env из образца при make setup."""

from urllib.parse import unquote

from sqlalchemy.engine import make_url

from tools.init_env import CONTAINER_SECRETS, ROOT, add_container_secrets, fill


def env_value(text, key):
    return next(line.split("=", 1)[1] for line in text.splitlines() if line.startswith(key + "="))


def test_password_and_secret_key_are_filled():
    text = fill((ROOT / ".env.example").read_text(encoding="utf-8"), "p@ss:w/rd")
    url = make_url(env_value(text, "DATABASE_URL"))
    assert unquote(url.password) == "p@ss:w/rd"
    assert url.host == "localhost"
    assert url.database == "sklad"
    assert len(env_value(text, "SECRET_KEY")) == 64
    assert "change-me" not in text


def test_container_passwords_are_random_and_different():
    text = fill((ROOT / ".env.example").read_text(encoding="utf-8"), "secret")
    postgres = env_value(text, "POSTGRES_PASSWORD")
    sklad = env_value(text, "SKLAD_DB_PASSWORD")
    assert len(postgres) == len(sklad) == 32
    assert postgres != sklad
    assert postgres.isalnum() and sklad.isalnum()


def test_test_database_keeps_its_name():
    text = fill((ROOT / ".env.test.example").read_text(encoding="utf-8"), "secret")
    url = make_url(env_value(text, "TEST_DATABASE_URL"))
    assert url.password == "secret"
    assert url.database == "sklad_test"


def test_container_passwords_added_to_old_env(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SECRET_KEY=abc", encoding="utf-8")  # без перевода строки в конце

    assert add_container_secrets(env) == list(CONTAINER_SECRETS)
    text = env.read_text(encoding="utf-8")
    assert text.startswith("SECRET_KEY=abc\n")
    assert len(env_value(text, "POSTGRES_PASSWORD")) == 32

    # повторный запуск ничего не меняет
    assert add_container_secrets(env) == []
    assert env.read_text(encoding="utf-8") == text


def test_existing_container_password_is_kept(tmp_path):
    env = tmp_path / ".env"
    env.write_text("POSTGRES_PASSWORD=mine\n", encoding="utf-8")
    assert add_container_secrets(env) == ["SKLAD_DB_PASSWORD"]
    assert env_value(env.read_text(encoding="utf-8"), "POSTGRES_PASSWORD") == "mine"
