"""Отдельный маленький updater-процесс (см. решение №4 в DEV_PLAN.md).

Собирается PyInstaller'ом в свой собственный, отдельный от лаунчера
исполняемый файл. Запускается лаунчером с двумя аргументами:

    app_updater <путь_к_установленному_лаунчеру> <url_архива_с_новой_версией>

и делает: дождаться закрытия лаунчера -> скачать zip -> распаковать ->
подменить старую копию новой -> запустить обновлённый лаунчер.

Адаптировано из older_projects/_Launcher/app_updater.py: та же логика поиска
процесса/ожидания закрытия, но подмена файла сделана кроссплатформенной —
на Windows заменяется один .exe, на macOS заменяется весь .app бандл
(директория), а не файл.
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
    launcher_path = launcher_path.resolve()
    for proc in psutil.process_iter(["pid", "exe"]):
        try:
            exe = proc.info["exe"]
            if not exe:
                continue
            exe_path = Path(exe).resolve()
            if _is_macos_bundle(launcher_path):
                if launcher_path in exe_path.parents:
                    return proc
            elif exe_path == launcher_path:
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
    else:
        candidates = list(extract_dir.rglob("*.exe"))

    if not candidates:
        raise RuntimeError("В архиве не найден новый лаунчер")
    return candidates[0]


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
    elif platform.system() == "Windows":
        subprocess.Popen([str(launcher_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
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
