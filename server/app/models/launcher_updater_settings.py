from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LauncherUpdaterSettings(Base):
    __tablename__ = "launcher_updater_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    updater_url_windows: Mapped[str | None] = mapped_column(String(2083))
    updater_url_macos: Mapped[str | None] = mapped_column(String(2083))
