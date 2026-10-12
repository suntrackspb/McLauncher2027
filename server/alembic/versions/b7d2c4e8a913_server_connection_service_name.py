"""server_connection.service_name

Revision ID: b7d2c4e8a913
Revises: a1c3e9d2f4b7
Create Date: 2026-10-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d2c4e8a913'
down_revision: Union[str, None] = 'a1c3e9d2f4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('server_connection', sa.Column('service_name', sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column('server_connection', 'service_name')
