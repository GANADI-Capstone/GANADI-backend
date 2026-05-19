"""user suspend_reason, vet opinion_fee_won

Revision ID: g9h0i1j2k3l4
Revises: 557af7f2f48d
Create Date: 2026-05-19

"""

from alembic import op
import sqlalchemy as sa


revision = "g9h0i1j2k3l4"
down_revision = "557af7f2f48d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("suspend_reason", sa.Text(), nullable=True))
    op.add_column("vets", sa.Column("opinion_fee_won", sa.Integer(), nullable=True))
    op.add_column("admin_reports", sa.Column("target_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_reports", "target_user_id")
    op.drop_column("vets", "opinion_fee_won")
    op.drop_column("users", "suspend_reason")
