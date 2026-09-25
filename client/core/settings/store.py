import json
import os
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path


def get_app_data_dir(app_folder_name: str) -> Path:
    """Кроссплатформенная папка данных приложения (аналог того, что делал
    launcher_gui.py вручную, но с учётом macOS)."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = str(Path.home() / ".local" / "share")

    path = Path(base) / app_folder_name
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class LauncherSettings:
    nickname: str = ""
    ram_mb: int = 4096
    resolution_width: int = 1280
    resolution_height: int = 720
    install_path: str = ""
    # ID опциональных модов (из /mods/optional), которые игрок себе включил —
    # хранится только локально, на сервер не синкается (решение из DEV_PLAN.md).
    enabled_optional_mod_ids: list[int] = field(default_factory=list)


class SettingsStore:
    def __init__(self, app_folder_name: str, filename: str = "settings.json"):
        self._path = get_app_data_dir(app_folder_name) / filename

    def load(self) -> LauncherSettings:
        if not self._path.exists():
            return LauncherSettings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return LauncherSettings()

        defaults = asdict(LauncherSettings())
        known = {**defaults, **{k: v for k, v in data.items() if k in defaults}}
        return LauncherSettings(**known)

    def save(self, settings: LauncherSettings) -> None:
        self._path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8"
        )
