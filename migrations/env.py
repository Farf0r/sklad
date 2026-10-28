from logging.config import fileConfig

from alembic import context

from app.database import Base, engine
from app.models import material, receipt, supplier, unit, user  # noqa: F401 — регистрирует модели

config = context.config

# при запуске из python -m app.cli migrate журнал уже настроен там
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Режим offline не используется: миграции применяются к базе из DATABASE_URL")
with engine.connect() as connection:
    run_migrations(connection)
