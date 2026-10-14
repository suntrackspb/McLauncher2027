"""mods.modrinth_project_id

Revision ID: c4f1a2b9d6e0
Revises: b7d2c4e8a913
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f1a2b9d6e0'
down_revision: Union[str, None] = 'b7d2c4e8a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mods', sa.Column('modrinth_project_id', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('mods', 'modrinth_project_id')
