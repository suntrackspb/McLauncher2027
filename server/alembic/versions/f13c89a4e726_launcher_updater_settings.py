"""Store independent download URLs for the launcher updater."""

import sqlalchemy as sa
from alembic import op

revision = "f13c89a4e726"
down_revision = "d902f28fe31a"


def upgrade() -> None:
    settings = op.create_table(
        "launcher_updater_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("updater_url_windows", sa.String(length=2083), nullable=True),
        sa.Column("updater_url_macos", sa.String(length=2083), nullable=True),
    )
    op.bulk_insert(settings, [{"id": 1}])


def downgrade() -> None:
    op.drop_table("launcher_updater_settings")
