from dataclasses import dataclass

from core.settings.store import LauncherSettings


@dataclass(frozen=True)
class ServerProfile:
    """Хардкод-профиль одной сборки лаунчера — один профиль на билд
    (см. решение в DEV_PLAN.md), без мультипрофильного UI/бэка."""

    mc_version: str
    loader: str
    loader_version: str | None
    server_address: str
    server_port: int


def build_jvm_arguments(ram_mb: int) -> list[str]:
    """G1GC-тюнинг и fml-флаги — перенесены из TECH_CONTEXT.md старого
    `_Launcher` (проверенный на практике набор для Forge на 2 неделях НГ-сессии)."""
    return [
        f"-Xmx{ram_mb}M",
        f"-Xms{min(ram_mb, 1024)}M",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+UseG1GC",
        "-XX:G1NewSizePercent=20",
        "-XX:G1ReservePercent=20",
        "-XX:MaxGCPauseMillis=50",
        "-XX:G1HeapRegionSize=32M",
        "-Dfml.ignoreInvalidMinecraftCertificates=true",
        "-Dfml.ignorePatchDiscrepancies=true",
    ]


def build_launch_options(
    *,
    username: str,
    uuid: str,
    access_token: str,
    settings: LauncherSettings,
    profile: ServerProfile,
    minecraft_directory: str,
) -> dict:
    return {
        "username": username,
        "uuid": uuid,
        "token": access_token,
        "jvmArguments": build_jvm_arguments(settings.ram_mb),
        "launcherName": "McLauncher2027",
        "launcherVersion": "1.0.0",
        "gameDirectory": minecraft_directory,
        "customResolution": True,
        "resolutionWidth": str(settings.resolution_width),
        "resolutionHeight": str(settings.resolution_height),
        "server": profile.server_address,
        "port": str(profile.server_port),
    }
