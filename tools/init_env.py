"""Файлы настроек .env и .env.test из образцов (последний шаг make setup).

Уже существующие файлы не перезаписываются. Пароль пользователя sklad в локальном
PostgreSQL спрашивается один раз и подставляется в оба файла, SECRET_KEY и пароли
контейнерного окружения генерируются случайные. Если в старом .env нет паролей для
контейнеров, они дописываются в конец файла.
"""

import getpass
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
FILES = {".env": ".env.example", ".env.test": ".env.test.example"}
# пароли PostgreSQL в контейнере db: только латиница и цифры, их не нужно экранировать
CONTAINER_SECRETS = ("POSTGRES_PASSWORD", "SKLAD_DB_PASSWORD")


def fill(template: str, password: str) -> str:
    # в строке подключения спецсимволы пароля (@, :, /) нужно экранировать
    text = template.replace("sklad:change-me@", f"sklad:{quote(password, safe='')}@")
    for name in CONTAINER_SECRETS:
        text = re.sub(rf"^{name}=.*$", f"{name}={secrets.token_hex(16)}", text, flags=re.MULTILINE)
    return text.replace("change-me-to-a-long-random-string", secrets.token_hex(32))


def add_container_secrets(path: Path) -> list[str]:
    """Дописывает в существующий .env недостающие пароли контейнеров, возвращает их имена."""
    text = path.read_text(encoding="utf-8")
    keys = {line.split("=", 1)[0].strip() for line in text.splitlines() if "=" in line}
    missing = [name for name in CONTAINER_SECRETS if name not in keys]
    if missing:
        lines = ["", "# Контейнерное окружение (make up): пароли PostgreSQL в контейнере db"]
        lines += [f"{name}={secrets.token_hex(16)}" for name in missing]
        if text and not text.endswith("\n"):
            text += "\n"
        path.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")
    return missing


def main():
    missing = [name for name in FILES if not (ROOT / name).exists()]
    if missing and sys.stdin.isatty():
        password = getpass.getpass("Пароль пользователя sklad в PostgreSQL: ")
        for name in missing:
            template = (ROOT / FILES[name]).read_text(encoding="utf-8")
            (ROOT / name).write_text(fill(template, password), encoding="utf-8")
            print(f"Создан {name}")
    elif missing:
        print(f"Нет файлов {', '.join(missing)}: создайте их по образцам *.example")
    else:
        print("Файлы .env и .env.test уже есть, их не меняем")

    env = ROOT / ".env"
    if env.exists():
        added = add_container_secrets(env)
        if added:
            print(f"В .env добавлены пароли для контейнеров: {', '.join(added)}")


if __name__ == "__main__":
    main()
