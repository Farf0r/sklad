"""Резервная копия базы и восстановление из неё.

Копию делает утилита PostgreSQL pg_dump в формате custom: один сжатый файл со схемой
и данными. Восстанавливает pg_restore: удаляет таблицы базы и создаёт их заново из копии
в одной транзакции, поэтому при ошибке база остаётся как была.
"""

import glob
import logging
import os
import shutil
import subprocess  # nosec B404 — запуск утилит резервного копирования базы
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import settings

logger = logging.getLogger(__name__)

# установщик PostgreSQL под Windows не добавляет утилиты в PATH
WINDOWS_PG_BIN = "C:/Program Files/PostgreSQL/*/bin"
BEFORE_RESTORE = "before-restore"


class BackupError(Exception):
    pass


def find_tool(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    for folder in sorted(glob.glob(WINDOWS_PG_BIN), reverse=True):
        candidate = Path(folder) / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    raise BackupError(
        f"Не найдена утилита {name}. Установите клиент PostgreSQL или добавьте его в PATH"
    )


def database_name() -> str:
    return make_url(settings.database_url).database or ""


def connection_env() -> dict:
    # параметры подключения передаются через переменные окружения,
    # чтобы пароль не попал в командную строку (её видно в списке процессов)
    url = make_url(settings.database_url)
    env = dict(os.environ)
    env["PGHOST"] = url.host or "localhost"
    env["PGPORT"] = str(url.port or 5432)
    env["PGUSER"] = url.username or ""
    env["PGDATABASE"] = database_name()
    env["PGCONNECT_TIMEOUT"] = "5"
    if url.password:
        env["PGPASSWORD"] = url.password
    return env


def run(command: list[str]):
    result = subprocess.run(  # nosec B603 — список аргументов без оболочки
        command, env=connection_env(), capture_output=True, text=True, errors="replace", check=False
    )
    if result.returncode != 0:
        tool = Path(command[0]).stem
        raise BackupError(f"{tool} завершился с ошибкой: {result.stderr.strip()}")


def backup_dir() -> Path:
    return Path(settings.backup_dir)


def create_backup(folder: Path | None = None, suffix: str = "") -> Path:
    folder = folder or backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{database_name()}_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    if suffix:
        name += f"_{suffix}"
    path = folder / f"{name}.dump"
    number = 1
    while path.exists():
        number += 1
        path = folder / f"{name}_{number}.dump"

    run(
        [find_tool("pg_dump"), "--format=custom", "--no-owner", "--no-privileges", f"--file={path}"]
    )
    logger.info("создана резервная копия %s", path)
    return path


def latest_backup(folder: Path | None = None) -> Path:
    folder = folder or backup_dir()
    files = [path for path in folder.glob("*.dump") if BEFORE_RESTORE not in path.name]
    if not files:
        raise BackupError(f"В каталоге {folder} нет резервных копий")
    # при одинаковом времени изменения новее та копия, у которой имя больше: ..._2.dump
    return max(files, key=lambda path: (path.stat().st_mtime, path.name))


def restore_backup(path: Path):
    if not path.is_file():
        raise BackupError(f"Файл {path} не найден")
    run(
        [
            find_tool("pg_restore"),
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--single-transaction",
            f"--dbname={database_name()}",
            str(path),
        ]
    )
    logger.info("база восстановлена из %s", path)
