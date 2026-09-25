"""Отдельный маленький updater-процесс (см. решение №4 в DEV_PLAN.md).

Собирается PyInstaller'ом в свой собственный, отдельный от лаунчера
исполняемый файл и публикуется как отдельный ассет GitHub-релиза — НЕ кладётся
в архив лаунчера. Лаунчер сам качает его во временную папку прямо перед
обновлением (см. ui_bridge/api.py::LauncherApi._download_updater) и запускает
с двумя аргументами:

    app_updater <путь_к_установленному_лаунчеру> <url_архива_с_новой_версией>

и делает: дождаться закрытия лаунчера -> скачать zip -> распаковать ->
подменить старую копию новой -> запустить обновлённый лаунчер. Сам себя не
удаляет (на Windows нельзя удалить файл собственного работающего .exe) —
оставшийся файл подчищает лаунчер при следующем старте
(core/updater/paths.py::cleanup_stale_updater).

Адаптировано из older_projects/_Launcher/app_updater.py: та же логика поиска
процесса/ожидания закрытия, но подмена файла сделана кроссплатформенной — и
на Windows, и на macOS PyInstaller собирает лаунчер в виде папки (onedir/
.app-бандл, см. client/build.spec), поэтому апдейтер всегда подменяет целиком
директорию, а не отдельный файл (см. core/updater/paths.py::resolve_launcher_path,
который приводит переданный из ui_bridge путь к нужному корню).
"""

import logging
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import psutil
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(tempfile.gettempdir()) / "mclauncher_updater.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("app_updater")


def _is_macos_bundle(path: Path) -> bool:
    return path.suffix == ".app"


def find_launcher_process(launcher_path: Path) -> psutil.Process | None:
    """`launcher_path` — всегда директория (onedir-папка или .app-бандл, см.
    resolve_launcher_path), поэтому ищем процесс, чей exe лежит где-то внутри
    неё, а не сравниваем пути напрямую."""
    launcher_path = launcher_path.resolve()
    for proc in psutil.process_iter(["pid", "exe"]):
        try:
            exe = proc.info["exe"]
            if not exe:
                continue
            exe_path = Path(exe).resolve()
            if launcher_path in exe_path.parents:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, ValueError):
            continue
    return None


def wait_for_launcher_close(launcher_path: Path, timeout: int = 30) -> bool:
    log.info("Ожидание закрытия лаунчера...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = find_launcher_process(launcher_path)
        if proc is None:
            return True
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except psutil.TimeoutExpired:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass
        time.sleep(0.5)
    return find_launcher_process(launcher_path) is None


def download_archive(url: str, destination: Path) -> None:
    log.info("Скачивание новой версии: %s", url)
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    with open(destination, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)
    with zipfile.ZipFile(destination) as zf:
        if zf.testzip() is not None:
            raise RuntimeError("Скачанный архив повреждён")


def extract_new_version(zip_path: Path, extract_dir: Path, launcher_path: Path) -> Path:
    log.info("Распаковка архива...")
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)

    if _is_macos_bundle(launcher_path):
        candidates = list(extract_dir.rglob("*.app"))
        if not candidates:
            raise RuntimeError("В архиве не найден новый лаунчер")
        return candidates[0]

    # Windows onedir: в архиве лежит папка с exe и зависимостями — нужно
    # вернуть саму эту папку (родителя exe), а не файл.
    exe_candidates = list(extract_dir.rglob("*.exe"))
    if not exe_candidates:
        raise RuntimeError("В архиве не найден новый лаунчер")
    return exe_candidates[0].parent


def replace_launcher(launcher_path: Path, new_path: Path) -> None:
    log.info("Замена лаунчера...")
    backup_path = launcher_path.with_name(launcher_path.name + ".old")
    if backup_path.exists():
        shutil.rmtree(backup_path) if backup_path.is_dir() else backup_path.unlink()

    if launcher_path.exists():
        launcher_path.rename(backup_path)

    if new_path.is_dir():
        shutil.copytree(new_path, launcher_path)
    else:
        shutil.copy2(new_path, launcher_path)

    if backup_path.is_dir():
        shutil.rmtree(backup_path, ignore_errors=True)
    elif backup_path.exists():
        backup_path.unlink(missing_ok=True)


def relaunch(launcher_path: Path) -> None:
    log.info("Запуск обновлённого лаунчера...")
    if _is_macos_bundle(launcher_path):
        subprocess.Popen(["open", str(launcher_path)])
        return

    if platform.system() == "Windows":
        exe_candidates = list(launcher_path.glob("*.exe"))
        if not exe_candidates:
            log.error("Не найден исполняемый файл лаунчера в %s", launcher_path)
            return
        creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen([str(exe_candidates[0])], creationflags=creation_flags)
        return

    subprocess.Popen([str(launcher_path)])


def run(launcher_path: str, download_url: str) -> bool:
    launcher_path_p = Path(launcher_path)
    temp_dir = Path(tempfile.gettempdir())
    zip_path = temp_dir / "mclauncher_update.zip"
    extract_dir = temp_dir / "mclauncher_update_extract"

    try:
        if not wait_for_launcher_close(launcher_path_p):
            log.error("Не удалось дождаться закрытия лаунчера")
            return False

        download_archive(download_url, zip_path)
        new_path = extract_new_version(zip_path, extract_dir, launcher_path_p)
        replace_launcher(launcher_path_p, new_path)
        relaunch(launcher_path_p)
        return True
    except Exception:
        log.exception("Обновление не удалось")
        return False
    finally:
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(extract_dir, ignore_errors=True)


def main() -> None:
    if len(sys.argv) < 3:
        print("Использование: app_updater <путь_к_лаунчеру> <url_архива>")
        sys.exit(1)
    success = run(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
