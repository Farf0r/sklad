"""Создание .env из образца при make setup."""

from urllib.parse import unquote

from sqlalchemy.engine import make_url

from tools.init_env import ROOT, fill


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


def test_test_database_keeps_its_name():
    text = fill((ROOT / ".env.test.example").read_text(encoding="utf-8"), "secret")
    url = make_url(env_value(text, "TEST_DATABASE_URL"))
    assert url.password == "secret"
    assert url.database == "sklad_test"
