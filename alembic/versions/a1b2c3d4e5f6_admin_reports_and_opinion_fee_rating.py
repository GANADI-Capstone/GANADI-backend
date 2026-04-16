"""admin_reports table and opinion service_fee / owner rating fields

Revision ID: a1b2c3d4e5f6
Revises: 6027e17c02fd
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "6027e17c02fd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opinions", sa.Column("service_fee", sa.Integer(), nullable=True))
    op.add_column("opinions", sa.Column("owner_rating", sa.Integer(), nullable=True))
    op.add_column("opinions", sa.Column("owner_review", sa.Text(), nullable=True))

    op.create_table(
        "admin_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=True),
        sa.Column("reporter_email", sa.String(length=255), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_label", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_reports_id"), "admin_reports", ["id"], unique=False)
    op.create_index(
        op.f("ix_admin_reports_created_at"), "admin_reports", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_reports_created_at"), table_name="admin_reports")
    op.drop_index(op.f("ix_admin_reports_id"), table_name="admin_reports")
    op.drop_table("admin_reports")
    op.drop_column("opinions", "owner_review")
    op.drop_column("opinions", "owner_rating")
    op.drop_column("opinions", "service_fee")
