import hashlib
from pathlib import Path

from app.core.config import settings
from app.services.errors import ServiceError

_MAX_TEXTURE_SIZE = 1024 * 1024  # 1 MB — с запасом для 64x64/64x32 PNG скина/плаща


def _storage_dir(texture_type: str) -> Path:
    path = Path(settings.textures_storage_dir) / texture_type
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_texture(texture_type: str, content: bytes) -> str:
    """Сохраняет PNG под именем-хешем (как PHP config.php::getSkinURL — файл
    называется md5 от содержимого, а не от игрока, поэтому одинаковые скины
    у разных игроков не дублируются на диске). Возвращает hex-хеш."""
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ServiceError("Файл должен быть PNG", error_code="BadRequest")
    if len(content) > _MAX_TEXTURE_SIZE:
        raise ServiceError("Файл слишком большой", error_code="BadRequest")

    file_hash = hashlib.md5(content).hexdigest()
    destination = _storage_dir(texture_type) / f"{file_hash}.png"
    if not destination.exists():
        destination.write_bytes(content)
    return file_hash


def texture_url(texture_type: str, texture_hash: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/textures/{texture_type}/{texture_hash}.png"
