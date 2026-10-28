"""Минимальный остаток материала

У материалов, которые уже есть в базе, минимальный остаток будет 0 — «не отслеживать».

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28 18:05:12
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "materials",
        sa.Column("min_stock", sa.Numeric(12, 3), server_default="0", nullable=False),
    )
    op.create_check_constraint("ck_materials_min_stock", "materials", "min_stock >= 0")


def downgrade():
    op.drop_constraint("ck_materials_min_stock", "materials", type_="check")
    op.drop_column("materials", "min_stock")
