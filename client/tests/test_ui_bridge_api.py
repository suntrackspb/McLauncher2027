from core.api_client.client import ApiError
from core.settings.store import LauncherSettings
from ui_bridge.api import LauncherApi


def _api_with_tmp_settings(tmp_path, mocker):
    mocker.patch("core.settings.store.get_app_data_dir", lambda name: tmp_path)
    return LauncherApi()


def test_get_settings_returns_defaults(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    assert api.get_settings() == {
        "nickname": "",
        "ram_mb": 4096,
        "resolution_width": 1280,
        "resolution_height": 720,
        "fullscreen": False,
        "java_path": "",
        "jvm_arguments_extra": "",
        "game_arguments_extra": "",
        "install_path": "",
        "enabled_optional_mod_ids": [],
    }


def test_save_settings_persists_and_ignores_unknown_fields(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    result = api.save_settings({"ram_mb": 8192, "hacked_field": "nope"})

    assert result["ram_mb"] == 8192
    assert "hacked_field" not in result
    assert api.get_settings()["ram_mb"] == 8192


def test_login_success_stores_session(mocker, tmp_path):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch.object(
        api._api_client,
        "login",
        return_value={"username": "steve", "UUID": "a" * 32, "accessToken": "b" * 32},
    )

    result = api.login("Steve", "pw")

    assert result["ok"] is True
    assert api.get_session() == {"username": "steve", "uuid": "a" * 32, "access_token": "b" * 32}


def test_login_failure_returns_error_and_no_session(mocker, tmp_path):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch.object(api._api_client, "login", side_effect=ApiError("Неверный логин или пароль"))

    result = api.login("Steve", "wrong")

    assert result["ok"] is False
    assert api.get_session() is None


def test_play_without_session_fails_fast(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    result = api.play()
    assert result == {"ok": False, "error": "Сначала войдите в аккаунт"}


def test_toggle_optional_mod_updates_settings(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)

    api.toggle_optional_mod(5, True)
    assert api.get_settings()["enabled_optional_mod_ids"] == [5]

    api.toggle_optional_mod(5, False)
    assert api.get_settings()["enabled_optional_mod_ids"] == []


def test_get_optional_mods_marks_enabled_flag(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    api.toggle_optional_mod(2, True)

    mocker.patch.object(
        api._api_client,
        "get_optional_mods",
        return_value=[
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
        ],
    )

    result = api.get_optional_mods()

    assert result["ok"] is True
    by_id = {m["id"]: m["enabled"] for m in result["data"]}
    assert by_id == {1: False, 2: True}


def test_check_for_update_reports_no_update(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch.object(
        api._api_client, "get_launcher_version", return_value={"version": "v1.0.0", "download_url_windows": "x"}
    )
    result = api.check_for_update()
    assert result == {"ok": True, "update_available": False}


def test_check_for_update_reports_available_update(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch("ui_bridge.api.LAUNCHER_VERSION", "1.0.0")
    mocker.patch.object(
        api._api_client,
        "get_launcher_version",
        return_value={
            "version": "1.1.0",
            "download_url_windows": "http://x/win.zip",
            "download_url_macos": "http://x/mac.zip",
            "updater_url_windows": "http://x/updater-win.exe",
            "updater_url_macos": "http://x/updater-mac",
        },
    )
    mocker.patch("core.updater.version_check.platform.system", return_value="Windows")
    result = api.check_for_update()
    assert result["ok"] is True
    assert result["update_available"] is True
    assert result["version"] == "1.1.0"
    assert result["updater_url"] == "http://x/updater-win.exe"


def test_check_for_update_wraps_api_error(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch.object(api._api_client, "get_launcher_version", side_effect=ApiError("Сервер недоступен"))
    assert api.check_for_update() == {"ok": False, "error": "Сервер недоступен"}


def test_start_update_fails_in_dev_mode(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    result = api.start_update("http://x/win.zip", "http://x/updater.exe")
    assert result == {"ok": False, "error": "Обновление доступно только в собранной версии лаунчера"}


def test_start_update_fails_when_updater_download_fails(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch("ui_bridge.api.sys.frozen", True, create=True)
    mocker.patch("ui_bridge.api.sys.executable", str(tmp_path / "Launcher" / "Launcher.exe"))
    mocker.patch("ui_bridge.api.requests.get", side_effect=OSError("boom"))

    result = api.start_update("http://x/win.zip", "http://x/updater.exe")

    assert result["ok"] is False
    assert "Не удалось скачать updater" in result["error"]


def test_start_update_downloads_updater_and_closes_window(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    install_root = tmp_path / "install"
    launcher_dir = install_root / "Launcher"
    launcher_dir.mkdir(parents=True)
    updater_path = tmp_path / "downloaded_updater"

    mocker.patch("ui_bridge.api.sys.frozen", True, create=True)
    mocker.patch("ui_bridge.api.sys.executable", str(launcher_dir / "Launcher.exe"))
    mocker.patch("ui_bridge.api.updater_binary_path", return_value=updater_path)
    response_mock = mocker.Mock(content=b"stub-binary")
    response_mock.raise_for_status = mocker.Mock()
    mocker.patch("ui_bridge.api.requests.get", return_value=response_mock)
    popen_mock = mocker.patch("ui_bridge.api.subprocess.Popen")
    api._window = mocker.Mock()

    result = api.start_update("http://x/win.zip", "http://x/updater.exe")

    assert result == {"ok": True}
    assert updater_path.read_bytes() == b"stub-binary"
    popen_mock.assert_called_once()
    args = popen_mock.call_args[0][0]
    assert args[0] == str(updater_path)
    api._window.destroy.assert_called_once()


def test_get_optional_mods_wraps_api_error(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch.object(api._api_client, "get_optional_mods", side_effect=ApiError("Сервер недоступен"))

    result = api.get_optional_mods()

    assert result == {"ok": False, "error": "Сервер недоступен"}
