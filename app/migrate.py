import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.database import engine

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
BASELINE = "0001"


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["configure_logger"] = False
    return config


def migrate(revision: str = "head"):
    """Приводит схему базы к указанной ревизии (по умолчанию к последней)."""
    tables = set(inspect(engine).get_table_names())
    config = alembic_config()
    if "alembic_version" not in tables and "units" in tables:
        # база создана версиями 0.1–0.2, где таблицы создавались при запуске;
        # её схема совпадает с миграцией 0001, поэтому отмечаем её этой версией
        logger.info("База без истории миграций, отмечаем её версией %s", BASELINE)
        command.stamp(config, BASELINE)
    command.upgrade(config, revision)
