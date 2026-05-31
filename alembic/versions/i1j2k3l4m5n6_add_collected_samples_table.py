"""add collected_samples table

Revision ID: i1j2k3l4m5n6
Revises: h0i1j2k3l4m5
Create Date: 2026-06-01

"""

from alembic import op
import sqlalchemy as sa


revision = "i1j2k3l4m5n6"
down_revision = "h0i1j2k3l4m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collected_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="user_upload"),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("image_storage_key", sa.String(length=500), nullable=True),
        sa.Column(
            "animal_type",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column("capture_device", sa.String(length=32), nullable=False),
        sa.Column("pet_breed", sa.String(length=100), nullable=True),
        sa.Column("pet_age", sa.Integer(), nullable=True),
        sa.Column("pet_gender", sa.String(length=20), nullable=True),
        sa.Column("ai_predictions", sa.JSON(), nullable=False),
        sa.Column("ai_top3", sa.JSON(), nullable=False),
        sa.Column("ai_all_diseases", sa.JSON(), nullable=False),
        sa.Column("ai_main_disease", sa.String(length=100), nullable=True),
        sa.Column("ai_is_normal", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("ai_model_version", sa.String(length=64), nullable=True),
        sa.Column("ai_checkpoint", sa.String(length=255), nullable=True),
        sa.Column("training_consent", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("consent_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("consent_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("label_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("confirmed_disease", sa.String(length=100), nullable=True),
        sa.Column("confirmed_severity", sa.String(length=32), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("exported_at", sa.DateTime(), nullable=True),
        sa.Column("export_batch_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnosis_results.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("diagnosis_id", name="uq_collected_samples_diagnosis_id"),
    )
    op.create_index("ix_collected_samples_label_status", "collected_samples", ["label_status"])
    op.create_index(
        "ix_collected_samples_animal_device",
        "collected_samples",
        ["animal_type", "capture_device"],
    )
    op.create_index(
        "ix_collected_samples_confirmed_disease",
        "collected_samples",
        ["confirmed_disease"],
    )
    op.create_index("ix_collected_samples_created_at", "collected_samples", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_collected_samples_created_at", table_name="collected_samples")
    op.drop_index("ix_collected_samples_confirmed_disease", table_name="collected_samples")
    op.drop_index("ix_collected_samples_animal_device", table_name="collected_samples")
    op.drop_index("ix_collected_samples_label_status", table_name="collected_samples")
    op.drop_table("collected_samples")
