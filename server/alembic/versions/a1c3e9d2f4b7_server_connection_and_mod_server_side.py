"""server connection + mods.server_side

Revision ID: a1c3e9d2f4b7
Revises: 7068bd742a2f
Create Date: 2026-10-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c3e9d2f4b7'
down_revision: Union[str, None] = '7068bd742a2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('mods', sa.Column('server_side', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        'server_connection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(length=8), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=128), nullable=False),
        sa.Column('password_enc', sa.Text(), nullable=True),
        sa.Column('private_key_enc', sa.Text(), nullable=True),
        sa.Column('host_key', sa.Text(), nullable=True),
        sa.Column('server_dir', sa.String(length=512), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('server_connection')
    op.drop_column('mods', 'server_side')
