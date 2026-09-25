from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    uuid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(60))
    access_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    server_id: Mapped[str | None] = mapped_column(String(41), nullable=True)
    # md5 файла текстуры (имя файла в сторадже — <hash>.png), как в PHP-версии
    # TaoGunner (config.php::getSkinURL) — не сам файл, только ссылка на него.
    skin_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cape_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
