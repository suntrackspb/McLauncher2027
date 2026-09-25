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


def test_get_optional_mods_wraps_api_error(tmp_path, mocker):
    api = _api_with_tmp_settings(tmp_path, mocker)
    mocker.patch.object(api._api_client, "get_optional_mods", side_effect=ApiError("Сервер недоступен"))

    result = api.get_optional_mods()

    assert result == {"ok": False, "error": "Сервер недоступен"}
