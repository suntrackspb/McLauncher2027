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
from core.debug_log import DebugLogger, debug_log_path, is_debug_flag_set
from core.launch.options_builder import ServerProfile
from core.launch.pipeline import prepare_and_get_launch_command
from core.launch.profile_store import save_installed_profile, sync_install_dir
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
        self._app_data_dir = get_app_data_dir(APP_FOLDER_NAME)
        self._settings_store = SettingsStore(APP_FOLDER_NAME)
        self._api_client = ApiClient(BACKEND_URL, timeout=API_TIMEOUT_SECONDS)
        self._session: dict | None = None
        self._minecraft_directory = str(self._app_data_dir / "minecraft")
        self._force_reinstall = False
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

    def get_launcher_version(self) -> str:
        return LAUNCHER_VERSION

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
            profile_data = self._api_client.get_profile()
            mods = self._api_client.get_optional_mods(
                profile_data["loader"], profile_data["mc_version"]
            )
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

    def reinstall(self) -> dict:
        """Принудительный снос и переустановка minecraft-директории (кнопка
        "Переустановить" в UI) — на случай битой установки, независимо от
        того, совпадает ли локально стоящий профиль с профилем сервера."""
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        self._force_reinstall = True
        threading.Thread(target=self._play_thread, daemon=True).start()
        return {"ok": True}

    def _play_thread(self) -> None:
        reporter = WebviewProgressReporter(self._window) if self._window else None
        settings = self._settings_store.load()
        force_reinstall, self._force_reinstall = self._force_reinstall, False
        debug_logger = DebugLogger(enabled=settings.debug or is_debug_flag_set())
        debug_logger.log(f"=== Запуск игры (force_reinstall={force_reinstall}) ===")
        debug_logger.log(f"launcher_version={LAUNCHER_VERSION}, backend={self._api_client.base_url}")
        try:
            if reporter:
                reporter.status("Проверка профиля сервера")
            profile_data = self._api_client.get_profile()
            profile = ServerProfile(
                mc_version=profile_data["mc_version"],
                loader=profile_data["loader"],
                loader_version=profile_data.get("loader_version"),
                server_address=profile_data["server_address"],
                server_port=profile_data["server_port"],
            )

            wiped = sync_install_dir(
                Path(self._minecraft_directory),
                self._app_data_dir,
                profile,
                force=force_reinstall,
            )
            debug_logger.log(f"Переустановка директории игры: {wiped}")
            if wiped and reporter:
                reporter.status("Профиль сборки изменился — переустановка")

            command = prepare_and_get_launch_command(
                minecraft_directory=self._minecraft_directory,
                profile=profile,
                username=self._session["username"],
                uuid=self._session["uuid"],
                access_token=self._session["access_token"],
                settings=settings,
                authlib_patched_jars_dir=AUTHLIB_PATCHED_DIR,
                api_client=self._api_client,
                launcher_name=APP_NAME,
                launcher_version=LAUNCHER_VERSION,
                reporter=reporter,
                debug_logger=debug_logger,
            )
            save_installed_profile(self._app_data_dir, profile)
        except Exception as exc:  # noqa: BLE001 — репортим в UI любую причину провала
            debug_logger.log(f"ОШИБКА: {exc!r}")
            if reporter:
                reporter.status(f"Ошибка: {exc}")
            return

        debug_logger.log("Запуск процесса игры…")
        if reporter:
            reporter.status("Запуск игры")
        subprocess.Popen(command, cwd=self._minecraft_directory)
