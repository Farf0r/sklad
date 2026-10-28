"""Ограничения на уровне базы: работают, даже если обойти проверки в коде приложения."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import engine


def insert_reference_data(conn):
    conn.execute(text("INSERT INTO units (name, short_name) VALUES ('Килограмм', 'кг')"))
    conn.execute(text("INSERT INTO materials (name, unit_id) VALUES ('Цемент', 1)"))
    conn.execute(text("INSERT INTO suppliers (name, inn) VALUES ('ООО СтройБаза', '7701234567')"))
    conn.execute(
        text("INSERT INTO users (username, password_hash, role) VALUES ('u', 'x', 'admin')")
    )
    conn.execute(
        text(
            "INSERT INTO receipts (supplier_id, receipt_date, status, created_by_id) "
            "VALUES (1, CURRENT_DATE, 'draft', 1)"
        )
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE materials SET stock = -1",
        "INSERT INTO receipt_items (receipt_id, material_id, quantity, price) VALUES (1, 1, 0, 10)",
        "INSERT INTO receipt_items (receipt_id, material_id, quantity, price) VALUES (1, 1, 1, -1)",
        "UPDATE receipts SET status = 'deleted'",
        "UPDATE users SET role = 'root'",
        "INSERT INTO materials (name, unit_id) VALUES ('Песок', 999)",
        "INSERT INTO suppliers (name, inn) VALUES ('Другой', '7701234567')",
    ],
)
def test_database_rejects_invalid_data(statement):
    with engine.begin() as conn:
        insert_reference_data(conn)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(statement))


def test_same_material_twice_in_receipt():
    with engine.begin() as conn:
        insert_reference_data(conn)
        conn.execute(
            text(
                "INSERT INTO receipt_items (receipt_id, material_id, quantity, price) "
                "VALUES (1, 1, 1, 10)"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO receipt_items (receipt_id, material_id, quantity, price) "
                "VALUES (1, 1, 2, 10)"
            )
        )


def test_receipt_items_deleted_with_receipt():
    with engine.begin() as conn:
        insert_reference_data(conn)
        conn.execute(
            text(
                "INSERT INTO receipt_items (receipt_id, material_id, quantity, price) "
                "VALUES (1, 1, 1, 10)"
            )
        )
        conn.execute(text("DELETE FROM receipts"))
        assert conn.execute(text("SELECT count(*) FROM receipt_items")).scalar_one() == 0
