import argparse
import getpass
import logging
import sys

from sqlalchemy import inspect

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

    args = parser.parse_args()

    if args.command == "migrate":
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        migrate()
        print("Схема базы данных актуальна")

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


if __name__ == "__main__":
    main()
