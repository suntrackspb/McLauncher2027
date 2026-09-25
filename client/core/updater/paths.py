import platform
import tempfile
from pathlib import Path


def updater_binary_path() -> Path:
    """Путь, по которому лаунчер качает свежий app_updater перед обновлением
    (см. ui_bridge/api.py::LauncherApi._download_updater) и куда апдейтер
    сам себя запускает — фиксированное имя во временной папке ОС."""
    name = "app_updater.exe" if platform.system() == "Windows" else "app_updater"
    return Path(tempfile.gettempdir()) / name


def cleanup_stale_updater() -> None:
    """К моменту следующего запуска лаунчера апдейтер уже точно закрылся
    (он сам его перезапускает и завершается), поэтому удалить оставшийся
    файл во временной папке безопасно — в отличие от попытки апдейтера
    удалить самого себя, пока он ещё выполняется (на Windows это вообще
    невозможно, файл запущенного .exe заблокирован). Паттерн взят из
    older_projects/GUI/console_launcher/launcher.py::_cleanup_updater."""
    updater_binary_path().unlink(missing_ok=True)


def resolve_launcher_path(executable_path: str) -> Path:
    """`sys.executable` внутри собранного PyInstaller-приложения (onedir,
    см. `build.spec`) указывает на бинарник, а не на то, что реально нужно
    подменять при обновлении:

    - на macOS `--windowed`-сборка всегда оборачивается в
      `X.app/Contents/MacOS/X` — подменять нужно весь `.app`-бандл;
    - на Windows onedir-сборка кладёт exe в папку рядом со всеми DLL/данными
      (`McLauncher2027/McLauncher2027.exe`) — подменять нужно всю эту папку,
      иначе после обновления в ней останутся файлы от старой версии.

    В обоих случаях результат — директория, которую апдейтер целиком заменяет
    новой (см. `client/updater/app_updater.py`)."""
    path = Path(executable_path)
    contents_macos = path.parent
    if contents_macos.name == "MacOS" and contents_macos.parent.name == "Contents":
        return contents_macos.parent.parent
    if path.suffix.lower() == ".exe":
        return path.parent
    return path
