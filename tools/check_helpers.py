"""Общее для проверок make migrations-check и make backup-check (этапы CI «Миграции»
и «Резервное копирование»).

Проверки работают только с отдельной тестовой базой, как и автотесты: адрес берётся из
переменной TEST_DATABASE_URL или из файла .env.test, имя базы обязано оканчиваться на _test,
потому что проверки удаляют в ней все данные. Рабочая база из .env не используется.
"""

import os
import secrets
import subprocess  # nosec B404 — запуск команд приложения этого же проекта
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent


class CheckFailed(Exception):
    pass


def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    env_file = ROOT / ".env.test"
    if not url and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.strip().partition("=")
            if key == "TEST_DATABASE_URL":
                url = value
    if not url:
        sys.exit("Не задана тестовая база: создайте .env.test по образцу .env.test.example")
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql") or not (parsed.database or "").endswith(
        "_test"
    ):
        sys.exit("TEST_DATABASE_URL должна указывать на базу PostgreSQL с именем *_test")
    return url


def use_test_database():
    """Подменяет настройки приложения до его импорта: всё идёт в тестовую базу."""
    os.environ.update(
        {
            "DATABASE_URL": test_database_url(),
            "SECRET_KEY": secrets.token_hex(16),
            "APP_ENV": "test",
            "LOG_FILE": "",
            "BCRYPT_ROUNDS": "4",
        }
    )


def run_app(*args: str, check=True, **env: str) -> str:
    """Запускает консольную команду приложения, как make migrate / make backup / make restore."""
    result = subprocess.run(  # nosec B603 — список аргументов без оболочки
        [sys.executable, "-m", "app.cli", *args],
        cwd=ROOT,
        # вывод команды в UTF-8 и под Windows, где кодировка консоли по умолчанию cp1251
        env={**os.environ, "PYTHONIOENCODING": "utf-8", **env},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = result.stdout + result.stderr
    if check and result.returncode != 0:
        tail = "\n".join(output.strip().splitlines()[-10:])
        raise CheckFailed(f"python -m app.cli {' '.join(args)} завершилась с ошибкой:\n{tail}")
    return output


step_no = 0


def step(text: str):
    global step_no
    step_no += 1
    print(f"{step_no}. {text}", flush=True)


def ok(text: str):
    print(f"     ok  {text}", flush=True)


def require(condition: bool, text: str):
    if not condition:
        raise CheckFailed(text)
    ok(text)
