import re
import shutil
from pathlib import Path

# Mojang кладёт authlib сюда: libraries/com/mojang/authlib/<версия>/authlib-<версия>.jar
_AUTHLIB_JAR_RE = re.compile(r"^authlib-(?P<version>[0-9][0-9.]*)\.jar$")


def find_authlib_jars(minecraft_directory: str | Path) -> list[Path]:
    """Оригинальные (не пропатченные) authlib-джары, поставленные
    minecraft-launcher-lib вместе с Vanilla/Forge/Fabric."""
    libs_root = Path(minecraft_directory) / "libraries" / "com" / "mojang" / "authlib"
    if not libs_root.exists():
        return []
    return sorted(p for p in libs_root.rglob("authlib-*.jar") if _AUTHLIB_JAR_RE.match(p.name))


def patch_authlib_jars(minecraft_directory: str | Path, patched_jars_dir: str | Path) -> list[Path]:
    """Подменяет authlib-<версия>.jar на заранее пропатченную версию с адресом
    нашего бэкенда — тот же ручной приём, что раньше делался вручную поверх
    джаров TaoGunner (см. older_projects/authlib_skinfix_by_TaoGunner-2), только
    автоматически при установке.

    Пропатченный джар должен лежать в `patched_jars_dir` под именем
    `authlib-<версия>_skinfix.jar`, версия должна совпадать 1-в-1 с оригиналом,
    который использует конкретная версия Minecraft/Forge/Fabric.

    Если для найденной версии нет пропатченного джара — она молча пропускается
    (значит, для этой версии Minecraft заготовка ещё не подготовлена).
    """
    patched_jars_dir = Path(patched_jars_dir)
    patched: list[Path] = []

    for original in find_authlib_jars(minecraft_directory):
        version = _AUTHLIB_JAR_RE.match(original.name).group("version")
        replacement = patched_jars_dir / f"authlib-{version}_skinfix.jar"
        if not replacement.is_file():
            continue
        shutil.copyfile(replacement, original)
        patched.append(original)

    return patched
