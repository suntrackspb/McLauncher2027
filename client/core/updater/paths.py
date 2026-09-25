from pathlib import Path


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
