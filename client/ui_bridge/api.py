import platform
import stat
import subprocess
import sys
import threading
from dataclasses import asdict, replace
from pathlib import Path

import requests
import webview

from core.api_client.client import ApiClient, ApiError
from core.launch.pipeline import prepare_and_get_launch_command
from core.settings.store import SettingsStore, get_app_data_dir
from core.updater.paths import cleanup_stale_updater, resolve_launcher_path, updater_binary_path
from core.updater.version_check import check_for_update
from ui_bridge.config import (
    API_TIMEOUT_SECONDS,
    APP_FOLDER_NAME,
    APP_NAME,
    AUTHLIB_PATCHED_DIR,
    BACKEND_URL,
    DOWNLOAD_TIMEOUT_SECONDS,
    LAUNCHER_VERSION,
    PROFILE,
)
from ui_bridge.reporter import WebviewProgressReporter


class LauncherApi:
    """Единственная точка контакта между `web/` (JS) и `core/`. Каждый публичный
    метод здесь — часть контракта с фронтом: меняя `web/`, ничего в `core/` не
    трогаем, пока сигнатуры этих методов остаются прежними.

    Все методы синхронные и JSON-сериализуемые (так требует pywebview.api).
    Долгие операции (`play`) не блокируют мост — уходят в отдельный поток и
    репортят статус/прогресс через `window.onLauncherStatus`/`onLauncherProgress`
    (см. reporter.py), а не через возврат значения.
    """

    def __init__(self) -> None:
        self._window = None
        self._settings_store = SettingsStore(APP_FOLDER_NAME)
        self._api_client = ApiClient(BACKEND_URL, timeout=API_TIMEOUT_SECONDS)
        self._session: dict | None = None
        self._minecraft_directory = str(get_app_data_dir(APP_FOLDER_NAME) / "minecraft")
        # Апдейтер удаляет себя не сам (на Windows нельзя удалить файл
        # собственного работающего .exe) — оставшийся с прошлого обновления
        # файл подчищаем здесь, при следующем старте лаунчера, когда апдейтер
        # уже точно закрылся (см. core/updater/paths.py::cleanup_stale_updater).
        cleanup_stale_updater()

    def set_window(self, window) -> None:
        """Вызывается из app.py после создания окна — раньше момента, когда
        pywebview.api сможет дёргать методы, window ещё не существует."""
        self._window = window

    # --- настройки -----------------------------------------------------

    def get_settings(self) -> dict:
        return asdict(self._settings_store.load())

    def save_settings(self, data: dict) -> dict:
        current = self._settings_store.load()
        known_fields = asdict(current).keys()
        updated = replace(current, **{k: v for k, v in data.items() if k in known_fields})
        self._settings_store.save(updated)
        return asdict(updated)

    # --- обновление лаунчера ----------------------------------------------

    def check_for_update(self) -> dict:
        try:
            info = check_for_update(LAUNCHER_VERSION, self._api_client)
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}
        if info is None:
            return {"ok": True, "update_available": False}
        return {
            "ok": True,
            "update_available": True,
            "version": info.version,
            "download_url": info.download_url,
            "updater_url": info.updater_url,
        }

    def start_update(self, download_url: str, updater_url: str) -> dict:
        """Качает свежий app_updater с бэкенда (сам он в архив лаунчера не
        входит — см. DEV_PLAN.md), запускает его и закрывает лаунчер. Апдейтер
        сам подменяет файлы, перезапускает лаунчер и удаляет себя (см.
        client/updater/app_updater.py)."""
        if not getattr(sys, "frozen", False):
            return {"ok": False, "error": "Обновление доступно только в собранной версии лаунчера"}

        launcher_path = resolve_launcher_path(sys.executable)
        try:
            updater_path = self._download_updater(updater_url)
        except Exception as exc:
            return {"ok": False, "error": f"Не удалось скачать updater: {exc}"}

        subprocess.Popen([str(updater_path), str(launcher_path), download_url])
        if self._window:
            self._window.destroy()
        return {"ok": True}

    @staticmethod
    def _download_updater(updater_url: str) -> Path:
        """Скачивает app_updater во временную папку (фиксированный путь — см.
        updater_binary_path) и на macOS/Linux ставит исполняемый бит (Windows
        его не требует)."""
        destination = updater_binary_path()
        response = requests.get(updater_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        response.raise_for_status()
        destination.write_bytes(response.content)
        if platform.system() != "Windows":
            destination.chmod(destination.stat().st_mode | stat.S_IEXEC)
        return destination

    def browse_java_path(self) -> str | None:
        """Открывает нативный диалог выбора исполняемого файла Java
        (аналог кнопки "Browse..." у Java path в TLauncher)."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(webview.FileDialog.OPEN)
        return result[0] if result else None

    # --- аккаунт ---------------------------------------------------------

    def register(self, username: str, password: str) -> dict:
        try:
            data = self._api_client.register(username, password)
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "data": data}

    def login(self, username: str, password: str) -> dict:
        try:
            data = self._api_client.login(username, password)
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}

        self._session = {
            "username": data["username"],
            "uuid": data["UUID"],
            "access_token": data["accessToken"],
        }
        return {"ok": True, "data": self._session}

    def logout(self) -> dict:
        self._session = None
        return {"ok": True}

    def get_session(self) -> dict | None:
        return self._session

    # --- опциональные моды -------------------------------------------------

    def get_optional_mods(self) -> dict:
        try:
            mods = self._api_client.get_optional_mods(PROFILE.loader, PROFILE.mc_version)
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}

        enabled_ids = set(self._settings_store.load().enabled_optional_mod_ids)
        for mod in mods:
            mod["enabled"] = mod["id"] in enabled_ids
        return {"ok": True, "data": mods}

    def toggle_optional_mod(self, mod_id: int, enabled: bool) -> dict:
        settings = self._settings_store.load()
        ids = set(settings.enabled_optional_mod_ids)
        ids.add(mod_id) if enabled else ids.discard(mod_id)
        settings.enabled_optional_mod_ids = sorted(ids)
        self._settings_store.save(settings)
        return {"ok": True}

    # --- запуск игры -----------------------------------------------------

    def play(self) -> dict:
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        threading.Thread(target=self._play_thread, daemon=True).start()
        return {"ok": True}

    def _play_thread(self) -> None:
        reporter = WebviewProgressReporter(self._window) if self._window else None
        settings = self._settings_store.load()
        try:
            command = prepare_and_get_launch_command(
                minecraft_directory=self._minecraft_directory,
                profile=PROFILE,
                username=self._session["username"],
                uuid=self._session["uuid"],
                access_token=self._session["access_token"],
                settings=settings,
                authlib_patched_jars_dir=AUTHLIB_PATCHED_DIR,
                api_client=self._api_client,
                launcher_name=APP_NAME,
                launcher_version=LAUNCHER_VERSION,
                reporter=reporter,
            )
        except Exception as exc:  # noqa: BLE001 — репортим в UI любую причину провала
            if reporter:
                reporter.status(f"Ошибка: {exc}")
            return

        if reporter:
            reporter.status("Запуск игры")
        subprocess.Popen(command, cwd=self._minecraft_directory)
