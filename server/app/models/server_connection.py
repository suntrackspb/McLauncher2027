from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServerConnection(Base):
    """Одна строка (id=1) — как админка достучится до файлов игрового сервера.

    ftp/ftps — хостинг с панелью: панель сама ставит и запускает сервер, мы
    только кладём моды и наш authlib. sftp — свой сервер по SSH: те же файлы
    плюс (дальше) управление и установка. Пароль и ключ хранятся
    зашифрованными (app/core/secret_box.py) и наружу не отдаются."""

    __tablename__ = "server_connection"

    id: Mapped[int] = mapped_column(primary_key=True)
    protocol: Mapped[str] = mapped_column(String(8))  # ftp / ftps / sftp
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String(128))
    password_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    private_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # SSH host key, запомненный при первом подключении (trust on first use) —
    # дальше подмена сервера не пройдёт молча.
    host_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Корень сервера: там лежат mods/, libraries/, server.properties.
    server_dir: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
