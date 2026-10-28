"""Индексы для поступлений

Список поступлений сортируется по дате, а при удалении материала база ищет строки
поступлений с этим материалом. Без индексов оба запроса читают таблицу целиком.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-28 18:21:40
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_receipts_receipt_date", "receipts", ["receipt_date"])
    op.create_index("ix_receipt_items_material_id", "receipt_items", ["material_id"])


def downgrade():
    op.drop_index("ix_receipt_items_material_id", table_name="receipt_items")
    op.drop_index("ix_receipts_receipt_date", table_name="receipts")
