import hashlib
from pathlib import Path

from app.core.config import settings
from app.services.errors import ServiceError

_MAX_MOD_SIZE = 200 * 1024 * 1024  # 200 MB — с запасом под тяжёлые модпаки


def _storage_dir() -> Path:
    path = Path(settings.mods_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_mod_file(content: bytes) -> tuple[str, int]:
    """Сохраняет jar под именем-хешем содержимого (как со скинами/плащами —
    см. texture_storage.py), возвращает (sha256, размер). Хеш совпадает с тем,
    что клиент считает сам при скачивании и сверяет в downloader.py."""
    if not content.startswith(b"PK\x03\x04"):
        raise ServiceError("Файл должен быть .jar (zip)", error_code="BadRequest")
    if len(content) > _MAX_MOD_SIZE:
        raise ServiceError("Файл слишком большой", error_code="BadRequest")

    file_hash = hashlib.sha256(content).hexdigest()
    destination = _storage_dir() / f"{file_hash}.jar"
    if not destination.exists():
        destination.write_bytes(content)
    return file_hash, len(content)


def mod_url(file_hash: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return f"{base}/mod-files/{file_hash}.jar"
