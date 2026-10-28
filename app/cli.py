import argparse
import getpass
import logging
import sys
from pathlib import Path

from sqlalchemy import inspect

from app.backup import (
    BEFORE_RESTORE,
    BackupError,
    create_backup,
    database_name,
    latest_backup,
    restore_backup,
)
from app.database import SessionLocal, engine
from app.errors import AppError
from app.migrate import migrate
from app.models.user import ROLES
from app.services.users import create_user


def main():
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="создать пользователя")
    create.add_argument("--username", required=True)
    create.add_argument("--role", choices=ROLES, default="storekeeper")

    commands.add_parser("migrate", help="применить миграции базы данных")

    commands.add_parser("backup", help="создать резервную копию базы")

    restore = commands.add_parser("restore", help="восстановить базу из резервной копии")
    restore.add_argument("file", nargs="?", help="файл копии; если не указан — последняя копия")
    restore.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")

    args = parser.parse_args()

    if args.command == "migrate":
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        migrate()
        print("Схема базы данных актуальна")

    if args.command == "backup":
        try:
            path = create_backup()
        except BackupError as exc:
            print(exc)
            sys.exit(1)
        print(f"Резервная копия создана: {path}")

    if args.command == "restore":
        try:
            restore_command(args)
        except BackupError as exc:
            print(exc)
            sys.exit(1)

    if args.command == "create-user":
        if "users" not in inspect(engine).get_table_names():
            print("В базе нет таблиц. Сначала примените миграции: make migrate")
            sys.exit(1)
        password = getpass.getpass("Пароль: ")
        if password != getpass.getpass("Повторите пароль: "):
            print("Пароли не совпадают")
            sys.exit(1)

        with SessionLocal() as db:
            try:
                user = create_user(db, args.username, password, args.role)
            except AppError as exc:
                print(exc.message)
                sys.exit(1)
        print(f"Пользователь {user.username} ({user.role}) создан")


def restore_command(args):
    path = Path(args.file) if args.file else latest_backup()
    if not path.is_file():
        raise BackupError(f"Файл {path} не найден")
    print(f"Все данные базы {database_name()} будут заменены данными из копии {path}")
    if not args.yes and input("Продолжить? Введите yes: ").strip().lower() != "yes":
        print("Восстановление отменено")
        sys.exit(1)
    # если восстановили не ту копию, к текущему состоянию можно вернуться
    current = create_backup(suffix=BEFORE_RESTORE)
    print(f"Текущее состояние сохранено: {current}")
    restore_backup(path)
    print("База восстановлена")


if __name__ == "__main__":
    main()
