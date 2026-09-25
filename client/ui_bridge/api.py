import subprocess
import threading
from dataclasses import asdict, replace

import webview

from core.api_client.client import ApiClient, ApiError
from core.launch.pipeline import prepare_and_get_launch_command
from core.settings.store import SettingsStore, get_app_data_dir
from ui_bridge.config import AUTHLIB_PATCHED_DIR, APP_FOLDER_NAME, BACKEND_URL, PROFILE
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
        self._api_client = ApiClient(BACKEND_URL)
        self._session: dict | None = None
        self._minecraft_directory = str(get_app_data_dir(APP_FOLDER_NAME) / "minecraft")

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
                reporter=reporter,
            )
        except Exception as exc:  # noqa: BLE001 — репортим в UI любую причину провала
            if reporter:
                reporter.status(f"Ошибка: {exc}")
            return

        if reporter:
            reporter.status("Запуск игры")
        subprocess.Popen(command, cwd=self._minecraft_directory)
