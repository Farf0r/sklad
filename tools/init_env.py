"""Файлы настроек .env и .env.test из образцов (последний шаг make setup).

Уже существующие файлы не меняются. Пароль пользователя sklad в PostgreSQL спрашивается
один раз и подставляется в оба файла, SECRET_KEY генерируется случайный.
"""

import getpass
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
FILES = {".env": ".env.example", ".env.test": ".env.test.example"}


def fill(template: str, password: str) -> str:
    # в строке подключения спецсимволы пароля (@, :, /) нужно экранировать
    text = template.replace("sklad:change-me@", f"sklad:{quote(password, safe='')}@")
    return text.replace("change-me-to-a-long-random-string", secrets.token_hex(32))


def main():
    missing = [name for name in FILES if not (ROOT / name).exists()]
    if not missing:
        print("Файлы .env и .env.test уже есть, их не меняем")
        return
    if not sys.stdin.isatty():
        print(f"Нет файлов {', '.join(missing)}: создайте их по образцам *.example")
        return

    password = getpass.getpass("Пароль пользователя sklad в PostgreSQL: ")
    for name in missing:
        template = (ROOT / FILES[name]).read_text(encoding="utf-8")
        (ROOT / name).write_text(fill(template, password), encoding="utf-8")
        print(f"Создан {name}")


if __name__ == "__main__":
    main()
