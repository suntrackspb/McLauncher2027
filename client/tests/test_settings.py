from core.settings.store import LauncherSettings, SettingsStore


def test_load_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.store.get_app_data_dir", lambda name: tmp_path)
    store = SettingsStore("TestLauncher")
    assert store.load() == LauncherSettings()


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.store.get_app_data_dir", lambda name: tmp_path)
    store = SettingsStore("TestLauncher")

    settings = LauncherSettings(nickname="Steve", ram_mb=8192, enabled_optional_mod_ids=[1, 3])
    store.save(settings)

    loaded = store.load()
    assert loaded == settings


def test_load_ignores_unknown_fields(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.store.get_app_data_dir", lambda name: tmp_path)
    (tmp_path / "settings.json").write_text('{"nickname": "Alex", "from_the_future": true}')

    store = SettingsStore("TestLauncher")
    loaded = store.load()

    assert loaded.nickname == "Alex"
    assert loaded.ram_mb == LauncherSettings().ram_mb


def test_load_recovers_from_corrupted_file(tmp_path, monkeypatch):
    monkeypatch.setattr("core.settings.store.get_app_data_dir", lambda name: tmp_path)
    (tmp_path / "settings.json").write_text("{not valid json")

    store = SettingsStore("TestLauncher")
    assert store.load() == LauncherSettings()
