import re
import shutil
from pathlib import Path

import requests

from core.api_client.client import ApiClient

# Mojang кладёт authlib сюда: libraries/com/mojang/authlib/<версия>/authlib-<версия>.jar
_AUTHLIB_JAR_RE = re.compile(r"^authlib-(?P<version>[0-9][0-9.]*)\.jar$")

_DOWNLOAD_TIMEOUT_SECONDS = 60


def find_authlib_jars(minecraft_directory: str | Path) -> list[Path]:
    """Оригинальные (не пропатченные) authlib-джары, поставленные
    minecraft-launcher-lib вместе с Vanilla/Forge/Fabric."""
    libs_root = Path(minecraft_directory) / "libraries" / "com" / "mojang" / "authlib"
    if not libs_root.exists():
        return []
    return sorted(p for p in libs_root.rglob("authlib-*.jar") if _AUTHLIB_JAR_RE.match(p.name))


def patch_authlib_jars(
    minecraft_directory: str | Path, api_client: ApiClient, cache_dir: str | Path
) -> list[Path]:
    """Подменяет authlib-<версия>.jar на заранее пропатченную версию с адресом
    нашего бэкенда — тот же ручной приём, что раньше делался вручную поверх
    джаров TaoGunner, только автоматически при установке.

    Пропатченные джары больше не зашиты в сборку лаунчера — сервер отдаёт их
    список (версия -> ссылка на скачивание) через GET /launcher/authlib-jars
    (кладутся туда руками при деплое, см. ops-чеклист в DEV_PLAN.md). Клиент
    качает нужную версию один раз и кэширует в `cache_dir`, повторные запуски
    используют уже скачанный файл без обращения к сети.

    Если для найденной версии нет пропатченного джара на сервере — она молча
    пропускается (значит, для этой версии Minecraft заготовка ещё не
    подготовлена)."""
    originals = find_authlib_jars(minecraft_directory)
    if not originals:
        return []

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    available = {jar["version"]: jar["url"] for jar in api_client.get_authlib_jars()}

    patched: list[Path] = []
    for original in originals:
        version = _AUTHLIB_JAR_RE.match(original.name).group("version")
        url = available.get(version)
        if not url:
            continue

        cached = cache_dir / f"authlib-{version}_skinfix.jar"
        if not cached.is_file():
            response = requests.get(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
            response.raise_for_status()
            cached.write_bytes(response.content)

        shutil.copyfile(cached, original)
        patched.append(original)

    return patched
