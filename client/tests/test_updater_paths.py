from core.updater.paths import resolve_launcher_path


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
