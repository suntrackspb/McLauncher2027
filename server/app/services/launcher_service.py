import time

import httpx

from app.core.config import settings
from app.schemas.launcher import LauncherVersionOut

_CACHE_TTL_SECONDS = 300
_cache: dict = {"expires_at": 0.0, "value": None}


def _pick_asset_url(assets: list[dict], hint: str, *, zip_only: bool) -> str:
    """Апдейтер и архив лаунчера могут делить один и тот же hint в имени
    ('windows'/'macos'), поэтому дополнительно различаем их по расширению —
    лаунчер всегда .zip (см. client-build.yml), апдейтер — голый бинарник."""
    for asset in assets:
        name = asset.get("name", "").lower()
        if hint.lower() not in name:
            continue
        if name.endswith(".zip") != zip_only:
            continue
        return asset.get("browser_download_url", "")
    return ""


_EMPTY_VERSION = LauncherVersionOut(
    version="",
    download_url_windows="",
    download_url_macos="",
    updater_url_windows="",
    updater_url_macos="",
)


async def _fetch_latest_release() -> LauncherVersionOut:
    if not settings.launcher_github_repo:
        return _EMPTY_VERSION

    url = f"https://api.github.com/repos/{settings.launcher_github_repo}/releases/latest"
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        response = await http_client.get(url, headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    data = response.json()

    assets = data.get("assets", [])
    return LauncherVersionOut(
        version=data.get("tag_name", ""),
        download_url_windows=_pick_asset_url(assets, settings.launcher_asset_windows_hint, zip_only=True),
        download_url_macos=_pick_asset_url(assets, settings.launcher_asset_macos_hint, zip_only=True),
        updater_url_windows=_pick_asset_url(assets, settings.launcher_asset_windows_hint, zip_only=False),
        updater_url_macos=_pick_asset_url(assets, settings.launcher_asset_macos_hint, zip_only=False),
    )


async def get_latest_version() -> LauncherVersionOut:
    """GitHub Releases API — публичный, но с лимитом 60 запросов/час на IP без
    токена; кэшируем на 5 минут, чтобы не упираться в лимит при нескольких
    игроках, запускающих лаунчер одновременно. При ошибке отдаём пустой
    результат — клиент просто не увидит доступного обновления."""
    now = time.monotonic()
    if _cache["value"] is not None and now < _cache["expires_at"]:
        return _cache["value"]

    try:
        value = await _fetch_latest_release()
    except httpx.HTTPError:
        return _EMPTY_VERSION

    _cache["value"] = value
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    return value
