import platform
from dataclasses import dataclass

from core.api_client.client import ApiClient


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    updater_url: str


def _field_for_platform(server_response: dict, macos_key: str, windows_key: str) -> str:
    system = platform.system()
    key = macos_key if system == "Darwin" else windows_key
    return server_response.get(key, "")


def check_for_update(current_version: str, api_client: ApiClient) -> UpdateInfo | None:
    """Сравнивает вшитую в сборку версию с той, что отдаёт бэкенд. Версии —
    простые строки (сравнение на равенство, без семвер-парсинга: версий у нас
    выходит одна-две в сезон, усложнять незачем)."""
    response = api_client.get_launcher_version()
    server_version = response.get("version", "")
    if not server_version or server_version == current_version:
        return None

    download_url = _field_for_platform(response, "download_url_macos", "download_url_windows")
    updater_url = _field_for_platform(response, "updater_url_macos", "updater_url_windows")
    if not download_url or not updater_url:
        return None

    return UpdateInfo(version=server_version, download_url=download_url, updater_url=updater_url)
