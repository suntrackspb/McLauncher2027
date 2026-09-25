import minecraft_launcher_lib as mll

from core.loaders.base import LoaderStrategy, ProgressReporter, to_callback_dict


class VanillaLoader(LoaderStrategy):
    name = "vanilla"

    def install(
        self,
        minecraft_directory: str,
        mc_version: str,
        loader_version: str | None = None,
        reporter: ProgressReporter | None = None,
    ) -> str:
        mll.install.install_minecraft_version(
            mc_version, minecraft_directory, callback=to_callback_dict(reporter)
        )
        return mc_version

    def is_installed(
        self, minecraft_directory: str, mc_version: str, loader_version: str | None = None
    ) -> bool:
        return mll.utils.is_version_valid(mc_version, minecraft_directory)

    def resolve_version_id(
        self, minecraft_directory: str, mc_version: str, loader_version: str | None = None
    ) -> str:
        return mc_version
