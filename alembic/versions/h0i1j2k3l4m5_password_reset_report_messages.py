"""password reset tokens, report messages, target_vet_id

Revision ID: h0i1j2k3l4m5
Revises: g9h0i1j2k3l4
Create Date: 2026-05-19

"""

from alembic import op
import sqlalchemy as sa


revision = "h0i1j2k3l4m5"
down_revision = "g9h0i1j2k3l4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_reports",
        sa.Column("target_vet_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_admin_reports_target_vet_id",
        "admin_reports",
        ["target_vet_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_admin_reports_target_vet_id",
        "admin_reports",
        "vets",
        ["target_vet_id"],
        ["id"],
    )

    op.create_table(
        "report_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("sender_role", sa.String(length=16), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=True),
        sa.Column("sender_vet_id", sa.Integer(), nullable=True),
        sa.Column("audience", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["admin_reports.id"]),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["sender_vet_id"], ["vets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_messages_report_id", "report_messages", ["report_id"])
    op.create_index("ix_report_messages_created_at", "report_messages", ["created_at"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_type", sa.String(length=8), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("vet_id", sa.Integer(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vet_id"], ["vets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_password_reset_tokens_vet_id",
        "password_reset_tokens",
        ["vet_id"],
        unique=False,
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_vet_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_index("ix_report_messages_created_at", table_name="report_messages")
    op.drop_index("ix_report_messages_report_id", table_name="report_messages")
    op.drop_table("report_messages")

    op.drop_constraint("fk_admin_reports_target_vet_id", "admin_reports", type_="foreignkey")
    op.drop_index("ix_admin_reports_target_vet_id", table_name="admin_reports")
    op.drop_column("admin_reports", "target_vet_id")
