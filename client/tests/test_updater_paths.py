from core.updater.paths import cleanup_stale_updater, resolve_launcher_path, updater_binary_path


def test_windows_onedir_exe_resolves_to_containing_folder():
    # Прямые слэши — тест гоняется и на macOS/Linux (posix Path не парсит
    # бэкслеши как разделители), реальная сборка на Windows использует
    # WindowsPath и корректно режет и обратные слэши.
    result = resolve_launcher_path("C:/Games/McLauncher2027/McLauncher2027.exe")
    assert result.name == "McLauncher2027"


def test_macos_bundle_binary_resolves_to_app_root():
    result = resolve_launcher_path("/Applications/McLauncher2027.app/Contents/MacOS/McLauncher2027")
    assert result.name == "McLauncher2027.app"


def test_plain_linux_path_returned_as_is():
    result = resolve_launcher_path("/opt/McLauncher2027/McLauncher2027")
    assert result.name == "McLauncher2027"


def test_cleanup_stale_updater_removes_existing_file(mocker, tmp_path):
    stub = tmp_path / "app_updater"
    stub.write_bytes(b"stub")
    mocker.patch("core.updater.paths.updater_binary_path", return_value=stub)

    cleanup_stale_updater()

    assert not stub.exists()


def test_cleanup_stale_updater_is_noop_when_nothing_to_clean(mocker, tmp_path):
    missing = tmp_path / "app_updater"
    mocker.patch("core.updater.paths.updater_binary_path", return_value=missing)

    cleanup_stale_updater()  # не должно бросать исключение


def test_updater_binary_path_uses_platform_specific_name(mocker):
    mocker.patch("core.updater.paths.platform.system", return_value="Windows")
    assert updater_binary_path().name == "app_updater.exe"

    mocker.patch("core.updater.paths.platform.system", return_value="Darwin")
    assert updater_binary_path().name == "app_updater"
