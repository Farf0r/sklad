"""Начальная схема: пользователи, справочники, поступления

Схема совпадает с той, что создавало приложение версий 0.1–0.2 при запуске.

Revision ID: 0001
Revises:
Create Date: 2026-10-28 16:26:36
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("inn", sa.String(12), nullable=False, unique=True),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(100)),
        sa.Column("address", sa.String(300)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("short_name", sa.String(10), nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("role in ('admin', 'storekeeper')", name="ck_users_role"),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id"), nullable=False),
        sa.Column("stock", sa.Numeric(12, 3), server_default="0", nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("stock >= 0", name="ck_materials_stock"),
    )
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("comment", sa.String(500)),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status in ('draft', 'posted')", name="ck_receipts_status"),
    )
    op.create_table(
        "receipt_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "receipt_id",
            sa.Integer(),
            sa.ForeignKey("receipts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("receipt_id", "material_id", name="uq_receipt_items_material"),
        sa.CheckConstraint("quantity > 0", name="ck_receipt_items_quantity"),
        sa.CheckConstraint("price >= 0", name="ck_receipt_items_price"),
    )


def downgrade():
    op.drop_table("receipt_items")
    op.drop_table("receipts")
    op.drop_table("materials")
    op.drop_table("users")
    op.drop_table("units")
    op.drop_table("suppliers")
