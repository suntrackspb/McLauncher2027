from pathlib import Path

from ui_bridge._version import LAUNCHER_VERSION

# Единственное место, где собраны все значения, которые правятся перед
# пересборкой/релизом (версия, адреса, тайминги) — раньше были раскиданы по
# core/ и ui_bridge/api.py, из-за чего было легко поправить что-то в одном
# месте и забыть про дубликат в другом (см. историю с рассинхроном
# LAUNCHER_VERSION/launcherVersion в options_builder.py).
# Профиль сервера (версия/loader/адрес) больше не хардкодится тут — лаунчер
# получает его с бэкенда через GET /api/v1/launcher/profile и сравнивает с
# локальным маркером установки (см. core/launch/profile_store.py), сам
# переустанавливаясь при изменении. Меняется через админ-панель на сервере,
# без пересборки лаунчера.

APP_NAME = "McNYWeekend2027"
APP_FOLDER_NAME = ".mcweekend2027"
# Обратный домен для macOS-бандла (build.spec) — идентификатор приложения,
# как ID пакета на других платформах.
BUNDLE_ID = "ru.spbwar.mclauncher2027"

BACKEND_URL = "http://127.0.0.1:8000"

# LAUNCHER_VERSION больше не хардкодится тут — CI сама прописывает его в
# ui_bridge/_version.py из git-тега перед сборкой релиза (см. workflow),
# чтобы сверка с /api/v1/launcher/version (бэкенд берёт версию из последнего
# GitHub Release) не зависела от того, не забыли ли обновить константу руками.

WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 650

API_TIMEOUT_SECONDS = 10.0
DOWNLOAD_TIMEOUT_SECONDS = 60

CLIENT_ROOT = Path(__file__).resolve().parent.parent
AUTHLIB_PATCHED_DIR = str(CLIENT_ROOT / "assets" / "authlib_patched")
