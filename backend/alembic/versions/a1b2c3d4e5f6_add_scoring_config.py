"""add scoring_config (global team scoring override)

Revision ID: a1b2c3d4e5f6
Revises: f3b079cf1d75
Create Date: 2026-06-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3b079cf1d75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scoring_config',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('health_weights_json', sa.JSON(), nullable=False),
        sa.Column('risk_weights_json', sa.JSON(), nullable=False),
        sa.Column('thresholds_json', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('scoring_config')
