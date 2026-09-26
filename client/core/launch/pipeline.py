from pathlib import Path

import minecraft_launcher_lib as mll

from core.api_client.client import ApiClient
from core.launch.authlib_patch import patch_authlib_jars
from core.launch.options_builder import ServerProfile, build_extra_game_arguments, build_launch_options
from core.loaders.base import ProgressReporter
from core.loaders.factory import get_loader
from core.settings.store import LauncherSettings
from core.sync.downloader import apply_sync_plan
from core.sync.mod_sync import plan_sync


def prepare_and_get_launch_command(
    *,
    minecraft_directory: str,
    profile: ServerProfile,
    username: str,
    uuid: str,
    access_token: str,
    settings: LauncherSettings,
    authlib_patched_jars_dir: str,
    api_client: ApiClient,
    launcher_name: str,
    launcher_version: str,
    reporter: ProgressReporter | None = None,
) -> list[str]:
    """Полный пайплайн одного запуска: установить лоадер -> синхронизировать
    моды с манифестом бэка -> подменить authlib -> собрать команду запуска.
    Ничего не знает про UI/pywebview — вызывается из ui_bridge."""

    loader = get_loader(profile.loader)
    version_id = loader.install(
        minecraft_directory, profile.mc_version, profile.loader_version, reporter
    )

    if reporter:
        reporter.status("Проверка модов")
    required = api_client.get_required_mods(profile.loader, profile.mc_version)
    optional = api_client.get_optional_mods(profile.loader, profile.mc_version)
    mods_dir = Path(minecraft_directory) / "mods"
    plan = plan_sync(required, optional, set(settings.enabled_optional_mod_ids), mods_dir)
    apply_sync_plan(plan, mods_dir, reporter)

    if reporter:
        reporter.status("Настройка авторизации")
    patch_authlib_jars(minecraft_directory, authlib_patched_jars_dir)

    options = build_launch_options(
        username=username,
        uuid=uuid,
        access_token=access_token,
        settings=settings,
        profile=profile,
        minecraft_directory=minecraft_directory,
        launcher_name=launcher_name,
        launcher_version=launcher_version,
    )
    command = mll.command.get_minecraft_command(version_id, minecraft_directory, options)
    command.extend(build_extra_game_arguments(settings))
    return command
