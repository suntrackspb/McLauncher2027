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
