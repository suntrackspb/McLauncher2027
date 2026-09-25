from pathlib import Path

from core.launch.options_builder import ServerProfile

# Один хардкод-профиль на билд лаунчера (решение из DEV_PLAN.md) — правим и
# пересобираем перед каждым релизом, без мультипрофильного UI/бэка.
APP_FOLDER_NAME = ".mclauncher2027"
BACKEND_URL = "http://127.0.0.1:8000"

# Правим при каждом релизе — сверяется с git-тегом, который отдаёт
# /api/v1/launcher/version (бэкенд берёт его из последнего GitHub Release).
LAUNCHER_VERSION = "v1.0.0"

PROFILE = ServerProfile(
    mc_version="1.20.1",
    loader="forge",
    loader_version="47.4.13",
    server_address="127.0.0.1",
    server_port=25565,
)

CLIENT_ROOT = Path(__file__).resolve().parent.parent
AUTHLIB_PATCHED_DIR = str(CLIENT_ROOT / "assets" / "authlib_patched")
