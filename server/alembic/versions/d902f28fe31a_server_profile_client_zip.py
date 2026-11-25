"""Add optional client ZIP URL to the server profile."""

import sqlalchemy as sa
from alembic import op

revision = "d902f28fe31a"
down_revision = "c4f1a2b9d6e0"


def upgrade() -> None:
    op.add_column(
        "server_profile", sa.Column("client_zip_url", sa.String(length=2083), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table("server_profile") as batch:
        batch.drop_column("client_zip_url")
