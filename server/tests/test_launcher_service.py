import httpx
import pytest

from app.core.config import settings
from app.services import launcher_service


@pytest.fixture(autouse=True)
def _reset_cache_and_repo():
    launcher_service._cache["value"] = None
    launcher_service._cache["expires_at"] = 0.0
    original_repo = settings.launcher_github_repo
    settings.launcher_github_repo = "example/repo"
    yield
    settings.launcher_github_repo = original_repo
    launcher_service._cache["value"] = None
    launcher_service._cache["expires_at"] = 0.0


def _fake_response(json_body, status_code=200):
    request = httpx.Request("GET", "https://api.github.com/repos/example/repo/releases/latest")
    return httpx.Response(status_code, json=json_body, request=request)


async def test_returns_empty_result_when_repo_not_configured(mocker):
    settings.launcher_github_repo = ""
    get_mock = mocker.patch("httpx.AsyncClient.get")

    result = await launcher_service.get_latest_version()

    assert result.version == ""
    get_mock.assert_not_called()


async def test_picks_assets_by_os_hint(mocker):
    mocker.patch(
        "httpx.AsyncClient.get",
        return_value=_fake_response(
            {
                "tag_name": "v1.2.0",
                "assets": [
                    {"name": "McLauncher2027-windows.zip", "browser_download_url": "http://x/win.zip"},
                    {"name": "McLauncher2027-macos.zip", "browser_download_url": "http://x/mac.zip"},
                ],
            }
        ),
    )

    result = await launcher_service.get_latest_version()

    assert result.version == "v1.2.0"
    assert result.download_url_windows == "http://x/win.zip"
    assert result.download_url_macos == "http://x/mac.zip"


async def test_caches_result_between_calls(mocker):
    get_mock = mocker.patch(
        "httpx.AsyncClient.get",
        return_value=_fake_response({"tag_name": "v1.0.0", "assets": []}),
    )

    await launcher_service.get_latest_version()
    await launcher_service.get_latest_version()

    assert get_mock.call_count == 1


async def test_returns_empty_result_on_http_error(mocker):
    mocker.patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("boom"))

    result = await launcher_service.get_latest_version()

    assert result.version == ""
    assert result.download_url_windows == ""
