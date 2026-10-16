import argparse
import getpass
import sys

from app.database import Base, SessionLocal, engine
from app.errors import AppError
from app.models.user import ROLES
from app.services.users import create_user


def main():
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="создать пользователя")
    create.add_argument("--username", required=True)
    create.add_argument("--role", choices=ROLES, default="storekeeper")

    args = parser.parse_args()

    if args.command == "create-user":
        password = getpass.getpass("Пароль: ")
        if password != getpass.getpass("Повторите пароль: "):
            print("Пароли не совпадают")
            sys.exit(1)

        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            try:
                user = create_user(db, args.username, password, args.role)
            except AppError as exc:
                print(exc.message)
                sys.exit(1)
        print(f"Пользователь {user.username} ({user.role}) создан")


if __name__ == "__main__":
    main()
