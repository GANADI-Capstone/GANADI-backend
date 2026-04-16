# script.py.mako
"""add vet profile columns and opinions table

Revision ID: cce16059d483
Revises: 6e6f44251e76
Create Date: 2026-04-14 20:50:39.816891

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cce16059d483'
down_revision = '6e6f44251e76'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vet 프로필 컬럼 추가
    op.add_column('vets', sa.Column('address', sa.String(length=255), nullable=True))
    op.add_column('vets', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('vets', sa.Column('specialty', sa.String(length=255), nullable=True))
    op.add_column('vets', sa.Column('business_hours', sa.String(length=255), nullable=True))

    # opinions 테이블 생성 (수의사 소견서)
    op.create_table(
        'opinions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('diagnosis_id', sa.Integer(), nullable=False),
        sa.Column('vet_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('visit_required', sa.Boolean(), nullable=True),
        sa.Column('symptom_memo', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['diagnosis_id'], ['diagnosis_results.id'], ),
        sa.ForeignKeyConstraint(['vet_id'], ['vets.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_opinions_id'), 'opinions', ['id'], unique=False)
    op.create_index(op.f('ix_opinions_diagnosis_id'), 'opinions', ['diagnosis_id'], unique=False)
    op.create_index(op.f('ix_opinions_vet_id'), 'opinions', ['vet_id'], unique=False)
    op.create_index(op.f('ix_opinions_created_at'), 'opinions', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_opinions_created_at'), table_name='opinions')
    op.drop_index(op.f('ix_opinions_vet_id'), table_name='opinions')
    op.drop_index(op.f('ix_opinions_diagnosis_id'), table_name='opinions')
    op.drop_index(op.f('ix_opinions_id'), table_name='opinions')
    op.drop_table('opinions')

    op.drop_column('vets', 'business_hours')
    op.drop_column('vets', 'specialty')
    op.drop_column('vets', 'phone')
    op.drop_column('vets', 'address')
