import hashlib
import struct
from pathlib import Path

from app.core.config import settings
from app.services.errors import ServiceError

_MAX_TEXTURE_SIZE = 1024 * 1024  # 1 MB — с запасом для 64x64/64x32 PNG скина/плаща


def _storage_dir(texture_type: str) -> Path:
    path = Path(settings.textures_storage_dir) / texture_type
    path.mkdir(parents=True, exist_ok=True)
    return path


def _png_size(content: bytes) -> tuple[int, int] | None:
    """Ширина/высота из IHDR — первый чанк PNG сразу после сигнатуры."""
    if len(content) < 24 or content[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", content[16:24])


def _is_valid_size(texture_type: str, width: int, height: int) -> bool:
    """Скин — 64x64 (с 1.8) или 64x32 (старый формат), плащ — 64x32 или
    старый 22x17. HD-варианты кратны 64 по ширине с теми же пропорциями."""
    if texture_type == "cape" and (width, height) == (22, 17):
        return True
    if width < 64 or width % 64 or width > 1024:
        return False
    if texture_type == "skin":
        return height in (width, width // 2)
    return height == width // 2


def save_texture(texture_type: str, content: bytes) -> str:
    """Сохраняет PNG под именем-хешем (как PHP config.php::getSkinURL — файл
    называется md5 от содержимого, а не от игрока, поэтому одинаковые скины
    у разных игроков не дублируются на диске). Возвращает hex-хеш."""
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ServiceError("Файл должен быть PNG", error_code="BadRequest")
    if len(content) > _MAX_TEXTURE_SIZE:
        raise ServiceError("Файл слишком большой", error_code="BadRequest")
    size = _png_size(content)
    if size is None or not _is_valid_size(texture_type, *size):
        expected = "64x64 или 64x32" if texture_type == "skin" else "64x32"
        raise ServiceError(f"Неверный размер картинки, нужен {expected}", error_code="BadRequest")

    file_hash = hashlib.md5(content).hexdigest()
    destination = _storage_dir(texture_type) / f"{file_hash}.png"
    if not destination.exists():
        destination.write_bytes(content)
    return file_hash


def texture_url(texture_type: str, texture_hash: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/textures/{texture_type}/{texture_hash}.png"
