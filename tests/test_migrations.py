from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.migrate import BASELINE, migrate


def empty_database():
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def current_revision():
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def schema_diff():
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)


def test_migrations_create_schema_from_scratch():
    empty_database()
    migrate()
    assert current_revision() == BASELINE
    assert schema_diff() == []


def test_old_database_is_stamped_and_keeps_data():
    # база версии 0.2: таблицы созданы без миграций, данные уже есть
    empty_database()
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO units (name, short_name) VALUES ('Килограмм', 'кг')"))

    migrate()

    assert current_revision() == BASELINE
    assert "alembic_version" in inspect(engine).get_table_names()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT short_name FROM units")).scalar_one() == "кг"
