import platform
from dataclasses import dataclass

from core.api_client.client import ApiClient


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str


def _download_url_for_platform(server_response: dict) -> str:
    system = platform.system()
    if system == "Darwin":
        return server_response.get("download_url_macos", "")
    return server_response.get("download_url_windows", "")


def check_for_update(current_version: str, api_client: ApiClient) -> UpdateInfo | None:
    """Сравнивает вшитую в сборку версию с той, что отдаёт бэкенд. Версии —
    простые строки (сравнение на равенство, без семвер-парсинга: версий у нас
    выходит одна-две в сезон, усложнять незачем)."""
    response = api_client.get_launcher_version()
    server_version = response.get("version", "")
    if not server_version or server_version == current_version:
        return None

    download_url = _download_url_for_platform(response)
    if not download_url:
        return None

    return UpdateInfo(version=server_version, download_url=download_url)
