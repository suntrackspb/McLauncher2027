import minecraft_launcher_lib as mll

from core.loaders.base import LoaderStrategy, ProgressReporter, to_callback_dict


class ModLoaderStrategy(LoaderStrategy):
    """Единая обёртка для всех лоадеров, которые minecraft-launcher-lib унифицировала
    в модуле `mod_loader` (forge/neoforge/fabric/quilt) — реальный API проверен
    инспекцией установленной библиотеки (v8.0), не документацией "на глаз"."""

    def __init__(self, loader_id: str):
        self.name = loader_id
        self._loader = mll.mod_loader.get_mod_loader(loader_id)

    def _pin_loader_version(self, mc_version: str, loader_version: str | None) -> str:
        return loader_version or self._loader.get_latest_loader_version(mc_version)

    def install(
        self,
        minecraft_directory: str,
        mc_version: str,
        loader_version: str | None = None,
        reporter: ProgressReporter | None = None,
    ) -> str:
        return self._loader.install(
            mc_version,
            minecraft_directory,
            loader_version=loader_version,
            callback=to_callback_dict(reporter),
        )

    def is_installed(
        self, minecraft_directory: str, mc_version: str, loader_version: str | None = None
    ) -> bool:
        try:
            version_id = self.resolve_version_id(minecraft_directory, mc_version, loader_version)
        except Exception:
            return False
        return mll.utils.is_version_valid(version_id, minecraft_directory)

    def resolve_version_id(
        self, minecraft_directory: str, mc_version: str, loader_version: str | None = None
    ) -> str:
        pinned = self._pin_loader_version(mc_version, loader_version)
        return self._loader.get_installed_version(mc_version, pinned)
