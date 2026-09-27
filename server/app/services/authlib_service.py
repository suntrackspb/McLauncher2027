import re
from pathlib import Path

from app.core.config import settings
from app.schemas.launcher import AuthlibJarOut

# Ожидаемое имя файла — то же, что раньше собиралось руками в
# client/assets/authlib_patched/ (см. core/launch/authlib_patch.py на клиенте):
# версия должна 1-в-1 совпадать с оригинальным authlib-<версия>.jar, который
# ставит minecraft-launcher-lib для конкретной версии Minecraft/loader'а.
_JAR_RE = re.compile(r"^authlib-(?P<version>[0-9][0-9.]*)_skinfix\.jar$")


def _storage_dir() -> Path:
    path = Path(settings.authlib_storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_jars() -> list[AuthlibJarOut]:
    """Сканирует папку с пропатченными jar'ами (кладутся туда руками при
    деплое — см. ops-чеклист в DEV_PLAN.md) и отдаёт список версия->ссылка на
    скачивание. Клиент сам решает, какая версия ему нужна (по оригинальному
    authlib-jar, который поставился вместе с его Minecraft/loader'ом)."""
    base = settings.public_base_url.rstrip("/")
    jars = []
    for path in sorted(_storage_dir().glob("authlib-*_skinfix.jar")):
        match = _JAR_RE.match(path.name)
        if not match:
            continue
        jars.append(
            AuthlibJarOut(version=match.group("version"), url=f"{base}/authlib-files/{path.name}")
        )
    return jars
