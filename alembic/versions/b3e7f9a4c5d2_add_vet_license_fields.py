"""add vet license/document fields and rejection reason

Revision ID: b3e7f9a4c5d2
Revises: a1b2c3d4e5f6
Create Date: 2026-05-02

"""
from alembic import op
import sqlalchemy as sa


revision = "b3e7f9a4c5d2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vets", sa.Column("license_number", sa.String(length=50), nullable=True))
    op.add_column("vets", sa.Column("license_image_url", sa.String(length=500), nullable=True))
    op.add_column("vets", sa.Column("employment_doc_url", sa.String(length=500), nullable=True))
    op.add_column("vets", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("vets", sa.Column("reviewed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("vets", "reviewed_at")
    op.drop_column("vets", "rejection_reason")
    op.drop_column("vets", "employment_doc_url")
    op.drop_column("vets", "license_image_url")
    op.drop_column("vets", "license_number")
