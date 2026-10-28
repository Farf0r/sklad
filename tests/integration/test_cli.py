import sys

import pytest

from app import cli
from app.database import SessionLocal
from app.services.users import authenticate


def run_cli(monkeypatch, *args, passwords=()):
    answers = iter(passwords)
    monkeypatch.setattr(sys, "argv", ["python -m app.cli", *args])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    cli.main()


def test_create_user(monkeypatch, capsys):
    run_cli(monkeypatch, "create-user", "--username", "kladovshik", passwords=["secret123"] * 2)
    assert "создан" in capsys.readouterr().out
    with SessionLocal() as db:
        assert authenticate(db, "kladovshik", "secret123").role == "storekeeper"


def test_create_user_passwords_do_not_match(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "create-user", "--username", "a", passwords=["secret123", "other123"])


def test_create_user_short_password(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "create-user", "--username", "a", passwords=["123", "123"])
    assert "не короче" in capsys.readouterr().out


def test_migrate_command(monkeypatch, capsys):
    run_cli(monkeypatch, "migrate")
    assert "Схема базы данных актуальна" in capsys.readouterr().out
