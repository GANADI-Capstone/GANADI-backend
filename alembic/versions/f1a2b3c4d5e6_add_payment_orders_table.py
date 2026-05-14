"""add payment_orders for Toss Payments (test mode)

Revision ID: f1a2b3c4d5e6
Revises: c1d2e3f4a5b6
Create Date: 2026-05-11

"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("toss_order_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payment_key", sa.String(length=200), nullable=True),
        sa.Column("vet_id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_id", sa.Integer(), nullable=False),
        sa.Column("symptom_memo", sa.Text(), nullable=True),
        sa.Column("opinion_id", sa.Integer(), nullable=True),
        sa.Column("webhook_last_status", sa.String(length=32), nullable=True),
        sa.Column("webhook_last_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnosis_results.id"]),
        sa.ForeignKeyConstraint(["opinion_id"], ["opinions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vet_id"], ["vets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payment_orders_toss_order_id"), "payment_orders", ["toss_order_id"], unique=True)
    op.create_index(op.f("ix_payment_orders_user_id"), "payment_orders", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_orders_user_id"), table_name="payment_orders")
    op.drop_index(op.f("ix_payment_orders_toss_order_id"), table_name="payment_orders")
    op.drop_table("payment_orders")
