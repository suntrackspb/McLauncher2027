import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ModType(str, enum.Enum):
    required = "required"
    optional = "optional"


class Mod(Base):
    __tablename__ = "mods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_name: Mapped[str] = mapped_column(String(256))
    url: Mapped[str] = mapped_column(String(512))
    file_hash: Mapped[str] = mapped_column(String(64))  # sha256
    size: Mapped[int] = mapped_column(Integer)
    mod_type: Mapped[ModType] = mapped_column(Enum(ModType))
    loader: Mapped[str] = mapped_column(String(32))  # forge / fabric / quilt / vanilla
    mc_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
