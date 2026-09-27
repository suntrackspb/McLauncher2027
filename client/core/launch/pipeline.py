from pathlib import Path

import minecraft_launcher_lib as mll

from core.api_client.client import ApiClient
from core.debug_log import DebugLogger
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
    authlib_cache_dir: str,
    api_client: ApiClient,
    launcher_name: str,
    launcher_version: str,
    reporter: ProgressReporter | None = None,
    debug_logger: DebugLogger | None = None,
) -> list[str]:
    """Полный пайплайн одного запуска: установить лоадер -> синхронизировать
    моды с манифестом бэка -> подменить authlib -> собрать команду запуска.
    Ничего не знает про UI/pywebview — вызывается из ui_bridge."""

    log = debug_logger.log if debug_logger else lambda *_a, **_k: None
    log_block = debug_logger.log_block if debug_logger else lambda *_a, **_k: None

    log_block(
        "Профиль сборки",
        {
            "mc_version": profile.mc_version,
            "loader": profile.loader,
            "loader_version": profile.loader_version,
            "server_address": profile.server_address,
            "server_port": profile.server_port,
        },
    )
    log(f"minecraft_directory={minecraft_directory}")
    log(f"username={username} uuid={uuid}")

    log(f"Установка loader'а '{profile.loader}'…")
    loader = get_loader(profile.loader)
    version_id = loader.install(
        minecraft_directory, profile.mc_version, profile.loader_version, reporter
    )
    log(f"Loader установлен, version_id={version_id}")

    if reporter:
        reporter.status("Проверка модов")
    required = api_client.get_required_mods(profile.loader, profile.mc_version)
    optional = api_client.get_optional_mods(profile.loader, profile.mc_version)
    log(f"Манифест модов: required={len(required)} optional={len(optional)}, "
        f"включено игроком={settings.enabled_optional_mod_ids}")
    mods_dir = Path(minecraft_directory) / "mods"
    plan = plan_sync(required, optional, set(settings.enabled_optional_mod_ids), mods_dir)
    log_block("План синхронизации модов", plan)
    apply_sync_plan(plan, mods_dir, reporter)
    log("Синхронизация модов завершена")

    if reporter:
        reporter.status("Настройка авторизации")
    patched = patch_authlib_jars(minecraft_directory, api_client, authlib_cache_dir)
    log(f"authlib пропатчен: {[str(p) for p in patched]}")

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
    log_block("Опции запуска (options)", options)

    command = mll.command.get_minecraft_command(version_id, minecraft_directory, options)
    command.extend(build_extra_game_arguments(settings))
    log_block("Итоговая команда запуска Minecraft", command)
    return command
