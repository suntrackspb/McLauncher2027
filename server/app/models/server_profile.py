from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServerProfile(Base):
    """Одна строка (id=1) — единственный профиль клиента (версия/loader/адрес
    сервера), который раньше был хардкодом в client/ui_bridge/config.py.
    Клиент сравнивает его с локальным маркером установки и переустанавливает
    minecraft-директорию целиком, если профиль изменился (см. DEV_PLAN.md)."""

    __tablename__ = "server_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    mc_version: Mapped[str] = mapped_column(String(32))
    loader: Mapped[str] = mapped_column(String(32))
    loader_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    server_address: Mapped[str] = mapped_column(String(255))
    server_port: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
