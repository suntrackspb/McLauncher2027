from core.launch.options_builder import ServerProfile
from core.launch.pipeline import prepare_and_get_launch_command
from core.settings.store import LauncherSettings

REQUIRED_MOD = {
    "id": 1,
    "name": "JEI",
    "file_name": "jei.jar",
    "url": "https://x/jei.jar",
    "file_hash": "irrelevant-because-download-is-mocked",
    "size": 10,
}


def test_pipeline_runs_all_steps_in_order(mocker, tmp_path):
    events = []

    fake_loader = mocker.Mock()
    fake_loader.install.side_effect = lambda *a, **k: events.append("install") or "1.20.1-forge-47.4.13"
    mocker.patch("core.launch.pipeline.get_loader", return_value=fake_loader)

    fake_api = mocker.Mock()
    fake_api.get_required_mods.return_value = [REQUIRED_MOD]
    fake_api.get_optional_mods.return_value = []

    mocker.patch(
        "core.launch.pipeline.apply_sync_plan",
        side_effect=lambda plan, mods_dir, reporter=None: events.append("sync_mods"),
    )
    mocker.patch(
        "core.launch.pipeline.patch_authlib_jars",
        side_effect=lambda *a, **k: events.append("patch_authlib") or [],
    )
    mocker.patch(
        "minecraft_launcher_lib.command.get_minecraft_command",
        side_effect=lambda *a, **k: events.append("build_command") or ["java", "-jar", "..."],
    )

    profile = ServerProfile(
        mc_version="1.20.1",
        loader="forge",
        loader_version="47.4.13",
        server_address="mc.example.com",
        server_port=25565,
    )

    command = prepare_and_get_launch_command(
        minecraft_directory=str(tmp_path),
        profile=profile,
        username="Steve",
        uuid="a" * 32,
        access_token="b" * 32,
        settings=LauncherSettings(),
        authlib_cache_dir=str(tmp_path / "authlib_cache"),
        api_client=fake_api,
        launcher_name="McLauncher2027",
        launcher_version="v1.0.0",
    )

    assert events == ["install", "sync_mods", "patch_authlib", "build_command"]
    assert command == ["java", "-jar", "..."]

    fake_loader.install.assert_called_once_with(str(tmp_path), "1.20.1", "47.4.13", None)
    fake_api.get_required_mods.assert_called_once_with("forge", "1.20.1")
    fake_api.get_optional_mods.assert_called_once_with("forge", "1.20.1")


def test_pipeline_passes_reporter_through_install(mocker, tmp_path):
    fake_loader = mocker.Mock()
    fake_loader.install.return_value = "1.20.1"
    mocker.patch("core.launch.pipeline.get_loader", return_value=fake_loader)

    fake_api = mocker.Mock()
    fake_api.get_required_mods.return_value = []
    fake_api.get_optional_mods.return_value = []

    mocker.patch("core.launch.pipeline.apply_sync_plan")
    mocker.patch("core.launch.pipeline.patch_authlib_jars", return_value=[])
    mocker.patch("minecraft_launcher_lib.command.get_minecraft_command", return_value=[])

    reporter = mocker.Mock()
    profile = ServerProfile(
        mc_version="1.20.1", loader="vanilla", loader_version=None,
        server_address="mc.example.com", server_port=25565,
    )

    prepare_and_get_launch_command(
        minecraft_directory=str(tmp_path),
        profile=profile,
        username="Steve",
        uuid="a" * 32,
        access_token="b" * 32,
        settings=LauncherSettings(),
        authlib_cache_dir=str(tmp_path / "authlib_cache"),
        api_client=fake_api,
        launcher_name="McLauncher2027",
        launcher_version="v1.0.0",
        reporter=reporter,
    )

    fake_loader.install.assert_called_once_with(str(tmp_path), "1.20.1", None, reporter)
    assert reporter.status.call_count >= 2


def test_zip_profile_keeps_the_archive_mods_instead_of_syncing_manifest(mocker, tmp_path):
    loader = mocker.patch("core.launch.pipeline.get_loader").return_value
    loader.install.return_value = "neoforge-26.1.2.128"
    patch_authlib = mocker.patch("core.launch.pipeline.patch_authlib_jars")
    mocker.patch("minecraft_launcher_lib.command.get_minecraft_command", return_value=["java"])
    api = mocker.Mock()
    mods = tmp_path / "mods"
    mods.mkdir()
    jar = mods / "from-archive.jar"
    jar.write_bytes(b"mod")
    profile = ServerProfile(
        mc_version="26.1.2", loader="neoforge", loader_version="26.1.2.128",
        server_address="mc.example.com", server_port=25565,
        client_zip_url="https://example.test/pack.zip",
    )

    command = prepare_and_get_launch_command(
        minecraft_directory=str(tmp_path), profile=profile, username="Steve",
        uuid="a" * 32, access_token="b" * 32, settings=LauncherSettings(),
        authlib_cache_dir=str(tmp_path / "cache"), api_client=api,
        launcher_name="McLauncher2027", launcher_version="v1.0.0",
    )

    assert command == ["java"]
    assert jar.read_bytes() == b"mod"
    api.get_required_mods.assert_not_called()
    api.get_optional_mods.assert_not_called()
    patch_authlib.assert_called_once()
