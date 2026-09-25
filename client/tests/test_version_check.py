from core.updater.version_check import UpdateInfo, check_for_update


class _FakeApiClient:
    def __init__(self, response):
        self._response = response

    def get_launcher_version(self):
        return self._response


def test_no_update_when_versions_match():
    api = _FakeApiClient({"version": "1.0.0", "download_url_windows": "http://x/win.zip"})
    assert check_for_update("1.0.0", api) is None


def test_update_available_when_versions_differ(mocker):
    mocker.patch("core.updater.version_check.platform.system", return_value="Windows")
    api = _FakeApiClient(
        {
            "version": "1.1.0",
            "download_url_windows": "http://x/win.zip",
            "download_url_macos": "http://x/mac.zip",
        }
    )
    result = check_for_update("1.0.0", api)
    assert result == UpdateInfo(version="1.1.0", download_url="http://x/win.zip")


def test_picks_macos_url_on_darwin(mocker):
    mocker.patch("core.updater.version_check.platform.system", return_value="Darwin")
    api = _FakeApiClient(
        {
            "version": "1.1.0",
            "download_url_windows": "http://x/win.zip",
            "download_url_macos": "http://x/mac.zip",
        }
    )
    result = check_for_update("1.0.0", api)
    assert result == UpdateInfo(version="1.1.0", download_url="http://x/mac.zip")


def test_no_update_when_download_url_missing_for_platform(mocker):
    mocker.patch("core.updater.version_check.platform.system", return_value="Darwin")
    api = _FakeApiClient({"version": "1.1.0", "download_url_windows": "http://x/win.zip", "download_url_macos": ""})
    assert check_for_update("1.0.0", api) is None
