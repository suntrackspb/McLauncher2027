import json
import shutil
from dataclasses import asdict
from pathlib import Path

from core.launch.options_builder import ServerProfile

MARKER_FILENAME = "installed_profile.json"


def _marker_path(app_data_dir: Path) -> Path:
    return app_data_dir / MARKER_FILENAME


def load_installed_profile(app_data_dir: Path) -> ServerProfile | None:
    path = _marker_path(app_data_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ServerProfile(**data)
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def save_installed_profile(app_data_dir: Path, profile: ServerProfile) -> None:
    _marker_path(app_data_dir).write_text(json.dumps(asdict(profile)), encoding="utf-8")


def sync_install_dir(
    minecraft_directory: Path, app_data_dir: Path, profile: ServerProfile, *, force: bool = False
) -> bool:
    """Если профиль с бэкенда отличается от того, что реально стоит локально
    (или `force=True` для ручной переустановки) — сносит содержимое
    minecraft-директории целиком, чтобы не тащить моды/либы от старого
    loader'а. Маркер удаляется ПЕРВЫМ, а не последним: если снос или
    установка прервутся (краш, отключение света, закрытие лаунчера — daemon-
    поток "плей" умирает вместе с процессом), на следующем запуске марker уже
    отсутствует и всё повторится с нуля само, без отдельного отслеживания
    "на чём именно прервались" (см. обсуждение в чате/DEV_PLAN.md).

    Возвращает True, если снос произошёл."""
    if not force and load_installed_profile(app_data_dir) == profile:
        return False

    _marker_path(app_data_dir).unlink(missing_ok=True)
    shutil.rmtree(minecraft_directory, ignore_errors=True)
    return True
