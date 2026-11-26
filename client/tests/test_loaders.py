import subprocess
from io import BytesIO
from pathlib import Path

import pytest

from core.loaders.factory import get_loader
from core.loaders.mod_loader_strategy import ModLoaderStrategy
from core.loaders.vanilla import VanillaLoader


def test_factory_returns_vanilla():
    assert isinstance(get_loader("vanilla"), VanillaLoader)


@pytest.mark.parametrize("loader_id", ["forge", "fabric", "quilt", "neoforge"])
def test_factory_returns_mod_loader_strategy(mocker, loader_id):
    mocker.patch("minecraft_launcher_lib.mod_loader.get_mod_loader")
    strategy = get_loader(loader_id)
    assert isinstance(strategy, ModLoaderStrategy)
    assert strategy.name == loader_id


def test_factory_rejects_unknown_loader():
    with pytest.raises(ValueError):
        get_loader("bedrock")


def test_vanilla_install_delegates_to_launcher_lib(mocker):
    install_mock = mocker.patch("minecraft_launcher_lib.install.install_minecraft_version")
    loader = VanillaLoader()

    version_id = loader.install("/tmp/mc", "1.20.1")

    assert version_id == "1.20.1"
    install_mock.assert_called_once()
    assert install_mock.call_args.args[0] == "1.20.1"
    assert install_mock.call_args.args[1] == "/tmp/mc"


def test_vanilla_is_installed_delegates_to_launcher_lib(mocker):
    mocker.patch("minecraft_launcher_lib.utils.is_version_valid", return_value=True)
    assert VanillaLoader().is_installed("/tmp/mc", "1.20.1") is True


def test_mod_loader_strategy_install_pins_loader_version(mocker):
    fake_loader = mocker.Mock()
    fake_loader.install.return_value = "forge-1.20.1-47.4.13"
    mocker.patch("minecraft_launcher_lib.mod_loader.get_mod_loader", return_value=fake_loader)

    strategy = ModLoaderStrategy("forge")
    version_id = strategy.install("/tmp/mc", "1.20.1", loader_version="47.4.13")

    assert version_id == "forge-1.20.1-47.4.13"
    fake_loader.install.assert_called_once()
    _, kwargs = fake_loader.install.call_args
    assert kwargs["loader_version"] == "47.4.13"


def test_neoforge_calendar_install_uses_minecraft_runtime_and_official_installer(mocker, tmp_path):
    install = mocker.patch("minecraft_launcher_lib.install.install_minecraft_version")
    mocker.patch(
        "minecraft_launcher_lib.runtime.get_version_runtime_information",
        return_value={"name": "java-runtime-epsilon", "javaMajorVersion": 25},
    )
    java_path = str(tmp_path / "runtime" / "java")
    executable = mocker.patch("minecraft_launcher_lib.runtime.get_executable_path", return_value=java_path)
    response = mocker.MagicMock()
    response.__enter__.return_value.raw = BytesIO(b"NeoForge installer")
    get = mocker.patch("core.loaders.mod_loader_strategy.requests.get", return_value=response)

    def run_installer(command, **kwargs):
        assert command[:2] == [java_path, "-jar"]
        assert Path(command[2]).read_bytes() == b"NeoForge installer"
        assert command[3:] == ["--install-client", str(tmp_path)]
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["capture_output"] is True
        return mocker.Mock(returncode=0)

    run = mocker.patch("core.loaders.mod_loader_strategy.subprocess.run", side_effect=run_installer)
    loader = get_loader("neoforge")

    assert loader.install(str(tmp_path), "26.1.2", "26.1.2.129") == "neoforge-26.1.2.129"
    assert [call.args for call in install.call_args_list] == [
        ("26.1.2", str(tmp_path)), ("neoforge-26.1.2.129", str(tmp_path)),
    ]
    executable.assert_called_once_with("java-runtime-epsilon", str(tmp_path))
    assert get.call_args.args[0].endswith("/26.1.2.129/neoforge-26.1.2.129-installer.jar")
    run.assert_called_once()


def test_neoforge_calendar_resolves_stable_matching_patch(mocker):
    get = mocker.patch("core.loaders.mod_loader_strategy.requests.get")
    get.return_value.json.return_value = {
        "versions": ["26.1.2.125", "26.1.2.129", "26.1.2.130-beta", "26.2.0.149"],
    }
    loader = get_loader("neoforge")

    assert loader.resolve_version_id("/tmp/mc", "26.1.2") == "neoforge-26.1.2.129"
    with pytest.raises(ValueError, match="несовместим"):
        loader.resolve_version_id("/tmp/mc", "26.1.2", "26.2.0.149")


def test_mod_loader_strategy_resolve_version_id_uses_latest_when_unset(mocker):
    fake_loader = mocker.Mock()
    fake_loader.get_latest_loader_version.return_value = "47.4.13"
    fake_loader.get_installed_version.return_value = "forge-1.20.1-47.4.13"
    mocker.patch("minecraft_launcher_lib.mod_loader.get_mod_loader", return_value=fake_loader)

    strategy = ModLoaderStrategy("forge")
    version_id = strategy.resolve_version_id("/tmp/mc", "1.20.1")

    assert version_id == "forge-1.20.1-47.4.13"
    fake_loader.get_latest_loader_version.assert_called_once_with("1.20.1")
    fake_loader.get_installed_version.assert_called_once_with("1.20.1", "47.4.13")


def test_mod_loader_strategy_is_installed_false_on_error(mocker):
    fake_loader = mocker.Mock()
    fake_loader.get_latest_loader_version.side_effect = RuntimeError("network down")
    mocker.patch("minecraft_launcher_lib.mod_loader.get_mod_loader", return_value=fake_loader)

    strategy = ModLoaderStrategy("fabric")
    assert strategy.is_installed("/tmp/mc", "1.20.1") is False


class _RecordingReporter:
    def __init__(self):
        self.statuses = []
        self.progresses = []

    def status(self, message):
        self.statuses.append(message)

    def progress(self, current, maximum):
        self.progresses.append((current, maximum))


def test_callback_dict_drops_per_file_statuses_and_translates_stages():
    from core.loaders.base import to_callback_dict

    reporter = _RecordingReporter()
    callback = to_callback_dict(reporter)
    callback["setStatus"]("Download Assets")
    callback["setStatus"]("Download f169c2bd7d40b3078e8e27c379904c3629f49482")
    callback["setStatus"]("Running forge installer")

    assert reporter.statuses == ["Загрузка ресурсов игры", "Running forge installer"]


def test_callback_dict_reports_progress_once_per_percent():
    from core.loaders.base import to_callback_dict

    reporter = _RecordingReporter()
    callback = to_callback_dict(reporter)
    callback["setMax"](1000)
    for i in range(1, 1001):
        callback["setProgress"](i)

    assert len(reporter.progresses) == 101  # 0%..100%
    assert reporter.progresses[-1] == (1000, 1000)
