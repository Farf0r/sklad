from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.migrate import BASELINE, alembic_config, migrate
from tests.conftest import drop_everything


def current_revision():
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def head_revision():
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def revisions():
    """Ревизии от первой к последней."""
    script = ScriptDirectory.from_config(alembic_config())
    return [rev.revision for rev in reversed(list(script.walk_revisions()))]


def schema_diff():
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        return compare_metadata(context, Base.metadata)


def test_clean_database_is_built_by_migrations():
    drop_everything()
    migrate()
    assert current_revision() == head_revision()
    assert schema_diff() == []


def test_models_match_migrations():
    # если модель изменили, а миграцию не написали, этот тест упадёт
    assert schema_diff() == []


def test_at_least_three_migrations():
    assert revisions()[:3] == ["0001", "0002", "0003"]


def test_each_migration_can_be_rolled_back():
    # откат и повтор по одному шагу: у каждой миграции рабочий downgrade
    config = alembic_config()
    for revision in reversed(revisions()):
        assert current_revision() == revision
        command.downgrade(config, "-1")
        command.upgrade(config, "+1")
        assert current_revision() == revision
        command.downgrade(config, "-1")
    assert current_revision() is None
    migrate()
    assert schema_diff() == []


def test_downgrade_to_base_and_upgrade_again():
    command.downgrade(alembic_config(), "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    migrate()
    assert current_revision() == head_revision()


def test_upgrade_keeps_existing_data():
    # база на первой версии схемы с данными, затем обновление до последней
    command.downgrade(alembic_config(), BASELINE)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO units (name, short_name) VALUES ('Килограмм', 'кг')"))
        conn.execute(
            text(
                "INSERT INTO materials (name, unit_id, stock) "
                "VALUES ('Цемент М500', (SELECT id FROM units), 40)"
            )
        )
    migrate()
    assert current_revision() == head_revision()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT name, stock, min_stock FROM materials")).one()
    assert row.name == "Цемент М500"
    assert row.stock == 40
    # у старых материалов минимальный остаток не задан
    assert row.min_stock == 0


def test_database_without_migration_history_is_stamped():
    # так выглядит база версий 0.1–0.2: схема 0001 есть, таблицы alembic_version нет
    drop_everything()
    command.upgrade(alembic_config(), BASELINE)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
        conn.execute(text("INSERT INTO units (name, short_name) VALUES ('Штука', 'шт')"))

    migrate()

    assert current_revision() == head_revision()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT short_name FROM units")).scalar_one() == "шт"
