import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import minecraft_launcher_lib as mll
import requests

from core.loaders.base import LoaderStrategy, ProgressReporter, to_callback_dict


_NEOFORGE_REPOSITORY = "https://maven.neoforged.net"
_NEOFORGE_ARTIFACT = "net/neoforged/neoforge"
_CALENDAR_VERSION = re.compile(r"\d{2}\.\d+(?:\.\d+)?")


class ModLoaderStrategy(LoaderStrategy):
    """Единая обёртка для всех лоадеров, которые minecraft-launcher-lib унифицировала
    в модуле `mod_loader` (forge/neoforge/fabric/quilt) — реальный API проверен
    инспекцией установленной библиотеки (v8.0), не документацией "на глаз"."""

    def __init__(self, loader_id: str):
        self.name = loader_id
        self._loader = mll.mod_loader.get_mod_loader(loader_id)

    def _pin_loader_version(self, mc_version: str, loader_version: str | None) -> str:
        if self.name == "neoforge" and _CALENDAR_VERSION.fullmatch(mc_version):
            release = mc_version if mc_version.count(".") == 2 else f"{mc_version}.0"
            compatible = re.compile(rf"{re.escape(release)}\.\d+(?:-[A-Za-z0-9.-]+)?")
            if loader_version:
                if not compatible.fullmatch(loader_version):
                    raise ValueError(f"NeoForge {loader_version} несовместим с Minecraft {mc_version}")
                return loader_version

            response = requests.get(
                f"{_NEOFORGE_REPOSITORY}/api/maven/versions/releases/{_NEOFORGE_ARTIFACT}",
                timeout=(10, 30),
            )
            response.raise_for_status()
            versions = [
                version for version in reversed(response.json()["versions"])
                if compatible.fullmatch(version)
            ]
            if not versions:
                raise mll.exceptions.UnsupportedVersion(mc_version)
            return next((version for version in versions if "-" not in version), versions[0])

        return loader_version or self._loader.get_latest_loader_version(mc_version)

    def install(
        self,
        minecraft_directory: str,
        mc_version: str,
        loader_version: str | None = None,
        reporter: ProgressReporter | None = None,
    ) -> str:
        if self.name == "neoforge" and _CALENDAR_VERSION.fullmatch(mc_version):
            version = self._pin_loader_version(mc_version, loader_version)
            return self._install_calendar_neoforge(minecraft_directory, mc_version, version, reporter)

        return self._loader.install(
            mc_version,
            minecraft_directory,
            loader_version=loader_version,
            callback=to_callback_dict(reporter),
        )

    def _install_calendar_neoforge(
        self, minecraft_directory: str, mc_version: str, version: str, reporter: ProgressReporter | None,
    ) -> str:
        # Version detection in minecraft-launcher-lib 8.0 assumes Minecraft is 1.x.
        directory = str(Path(minecraft_directory).resolve())
        callback = to_callback_dict(reporter)
        mll.install.install_minecraft_version(mc_version, directory, callback=callback)
        runtime = mll.runtime.get_version_runtime_information(mc_version, directory)
        java = mll.runtime.get_executable_path(runtime["name"], directory) if runtime else None
        if not java:
            raise RuntimeError(f"Не удалось найти Java для Minecraft {mc_version}")

        if not mll.vanilla_launcher.do_vanilla_launcher_profiles_exists(directory):
            mll.vanilla_launcher.create_empty_vanilla_launcher_profiles_file(directory)

        filename = f"neoforge-{version}-installer.jar"
        url = f"{_NEOFORGE_REPOSITORY}/releases/{_NEOFORGE_ARTIFACT}/{version}/{filename}"
        if reporter:
            reporter.status("Установка NeoForge")
        with TemporaryDirectory(prefix="neoforge-") as temp:
            installer = Path(temp) / filename
            with requests.get(url, stream=True, timeout=(10, 60)) as response:
                response.raise_for_status()
                with installer.open("wb") as output:
                    shutil.copyfileobj(response.raw, output)
            result = subprocess.run(
                [java, "-jar", str(installer), "--install-client", directory],
                cwd=temp,
                capture_output=True,
                text=True,
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode:
                details = (result.stderr.strip() or result.stdout.strip()).splitlines()
                summary = details[-1] if details else f"код выхода {result.returncode}"
                raise RuntimeError(f"Не удалось установить NeoForge {version}: {summary}")

        installed = self._loader.get_installed_version(mc_version, version)
        mll.install.install_minecraft_version(installed, directory, callback=callback)
        return installed

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
