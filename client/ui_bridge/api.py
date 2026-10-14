import base64
import os
import platform
import stat
import subprocess
import sys
import threading
from dataclasses import asdict, replace
from pathlib import Path
from urllib.parse import urlparse

import requests
import webview

from core.api_client.client import ApiClient, ApiError
from core.debug_log import DebugLogger, debug_log_path, is_debug_flag_set
from core.launch.options_builder import ServerProfile
from core.launch.pipeline import prepare_and_get_launch_command
from core.launch.servers_dat import write_server_bookmark
from core.launch.profile_store import load_installed_profile, save_installed_profile, sync_install_dir
from core.settings.session_store import SessionStore
from core.settings.store import SettingsStore, get_app_data_dir
from core.textures import TEXTURE_KINDS, check_texture
from core.updater.paths import cleanup_stale_updater, resolve_launcher_path, updater_binary_path
from core.updater.version_check import check_for_update
from ui_bridge.config import (
    API_TIMEOUT_SECONDS,
    APP_FOLDER_NAME,
    APP_NAME,
    BACKEND_URL,
    DOWNLOAD_TIMEOUT_SECONDS,
    LAUNCHER_VERSION,
)
from ui_bridge.reporter import WebviewProgressReporter


def _server_address(profile: ServerProfile) -> str:
    """Адрес для списка серверов: стандартный порт игра подставит сама."""
    if profile.server_port == 25565:
        return profile.server_address
    return f"{profile.server_address}:{profile.server_port}"


def _describe_error(exc: Exception) -> str:
    """Сетевые ошибки requests — это многострочное полотно про пулы соединений;
    в UI показываем, к какому серверу не достучались и что делать."""
    if isinstance(exc, requests.ConnectionError):
        url = getattr(exc.request, "url", None) or ""
        server = urlparse(url).hostname or "сервером загрузки"
        return (
            f"нет связи с {server}. Проверьте интернет и нажмите кнопку ещё раз — "
            "уже скачанные файлы повторно качаться не будут"
        )
    if isinstance(exc, requests.Timeout):
        return "сервер загрузки не ответил вовремя. Нажмите кнопку ещё раз"
    return str(exc)


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
        self._session_store = SessionStore(self._app_data_dir)
        self._session: dict | None = self._session_store.load()
        # Подготовка (установка/моды) и сама игра — одна "сессия запуска":
        # пока она идёт, повторный play/reinstall отклоняется, иначе вторая
        # копия игры или параллельная установка в ту же папку.
        self._launch_lock = threading.Lock()
        self._launch_busy = False
        self._game_process: subprocess.Popen | None = None
        self._game_killed = False
        self._minecraft_directory = str(self._app_data_dir / "minecraft")
        self._authlib_cache_dir = str(self._app_data_dir / "authlib_cache")
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

    # Границы числовых настроек: пустое поле в UI даёт 0, а -Xmx0M или окно
    # 0x0 ломают запуск игры.
    _INT_LIMITS = {
        "ram_mb": (512, 65536),
        "resolution_width": (320, 7680),
        "resolution_height": (240, 4320),
    }

    def save_settings(self, data: dict) -> dict:
        current = self._settings_store.load()
        values = {k: v for k, v in data.items() if k in asdict(current)}
        for key, (low, high) in self._INT_LIMITS.items():
            if key not in values:
                continue
            try:
                number = int(values[key])
            except (TypeError, ValueError):
                number = 0
            # Мусор/ноль — оставляем прежнее значение, иначе зажимаем в границы.
            values[key] = min(max(number, low), high) if number > 0 else getattr(current, key)
        updated = replace(current, **values)
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
        self._session_store.save(self._session)
        return {"ok": True, "data": self._session}

    def logout(self) -> dict:
        # Поток запуска читает self._session — пока он идёт, выходить нельзя.
        with self._launch_lock:
            if self._launch_busy:
                return {"ok": False, "error": "Нельзя выйти, пока идёт запуск или открыта игра"}
            self._session = None
        self._session_store.clear()
        return {"ok": True}

    def get_session(self) -> dict | None:
        return self._session

    # --- скин и плащ ------------------------------------------------------

    def get_textures(self) -> dict:
        """Текущие скин/плащ игрока как data:-URL — фронт рисует превью на
        canvas, а картинка с другого origin (бэкенд) "испортила" бы canvas."""
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        try:
            urls = self._api_client.get_texture_urls(self._session["uuid"])
            data = {
                kind: self._to_data_url(self._api_client.download_bytes(urls[kind])) if kind in urls else None
                for kind in TEXTURE_KINDS
            }
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "data": data}

    def upload_texture(self, kind: str) -> dict:
        """Нативный диалог выбора PNG -> проверка -> загрузка на бэкенд.
        {"ok": True, "cancelled": True}, если игрок закрыл диалог."""
        if kind not in TEXTURE_KINDS:
            return {"ok": False, "error": f"Неизвестный тип текстуры: {kind}"}
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        if not self._window:
            return {"ok": False, "error": "Окно лаунчера недоступно"}

        picked = self._window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("PNG (*.png)",)
        )
        if not picked:
            return {"ok": True, "cancelled": True}

        try:
            content = Path(picked[0]).read_bytes()
        except OSError as exc:
            return {"ok": False, "error": f"Не удалось прочитать файл: {exc}"}
        error = check_texture(kind, content)
        if error:
            return {"ok": False, "error": error}

        try:
            self._api_client.upload_texture(
                kind, self._session["uuid"], self._session["access_token"], content
            )
        except ApiError as exc:
            if exc.status_code == 403:
                return {"ok": False, "error": "Сессия устарела — выйдите и войдите снова"}
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "data_url": self._to_data_url(content)}

    def delete_texture(self, kind: str) -> dict:
        if kind not in TEXTURE_KINDS:
            return {"ok": False, "error": f"Неизвестный тип текстуры: {kind}"}
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        try:
            self._api_client.delete_texture(kind, self._session["uuid"], self._session["access_token"])
        except ApiError as exc:
            if exc.status_code == 403:
                return {"ok": False, "error": "Сессия устарела — выйдите и войдите снова"}
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    @staticmethod
    def _to_data_url(content: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(content).decode()

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
        try:
            self._settings_store.save(settings)
        except OSError as exc:
            return {"ok": False, "error": f"Не удалось сохранить настройки: {exc}"}
        return {"ok": True}

    # --- запуск игры -----------------------------------------------------

    def get_profile(self) -> dict:
        """Профиль сборки с бэка — показываем в UI, что именно будет
        установлено/запущено. Ошибку сети не пробрасываем: это лишь подпись."""
        try:
            return {"ok": True, "profile": self._api_client.get_profile()}
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}

    def is_installed(self) -> bool:
        """Есть ли локально установленная сборка — от этого зависит надпись
        на главной кнопке (PLAY или INSTALL). Совпадение с профилем сервера
        не проверяем: это сетевой запрос, а play() сам доустановит отличия."""
        return load_installed_profile(self._app_data_dir) is not None

    def play(self) -> dict:
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        return self._start_launch()

    def reinstall(self) -> dict:
        """Принудительный снос и переустановка minecraft-директории (кнопка
        "Переустановить" в UI) — на случай битой установки, независимо от
        того, совпадает ли локально стоящий профиль с профилем сервера."""
        if not self._session:
            return {"ok": False, "error": "Сначала войдите в аккаунт"}
        self._force_reinstall = True
        result = self._start_launch()
        if not result["ok"]:
            self._force_reinstall = False
        return result

    def get_game_state(self) -> dict:
        """Для фронта после перезагрузки страницы — идёт ли сейчас
        подготовка (busy) и запущена ли игра (running)."""
        return {"busy": self._launch_busy, "running": self._game_process is not None}

    def kill_game(self) -> dict:
        """Принудительно закрыть игру: сначала terminate (SIGTERM, игра
        успевает сохранить настройки), через 5 с — kill."""
        process = self._game_process
        if process is None:
            return {"ok": False, "error": "Игра не запущена"}
        self._game_killed = True
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        return {"ok": True}

    def open_game_folder(self) -> dict:
        """Открывает папку установки Minecraft в Finder/Проводнике."""
        folder = Path(self._minecraft_directory)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(folder)  # noqa: S606 — своя папка, не пользовательский ввод
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            return {"ok": False, "error": f"Не удалось открыть папку: {exc}"}
        return {"ok": True}

    def _start_launch(self) -> dict:
        with self._launch_lock:
            if self._launch_busy:
                running = self._game_process is not None
                return {"ok": False, "error": "Игра уже запущена" if running else "Запуск уже идёт"}
            self._launch_busy = True
        threading.Thread(target=self._launch_thread, daemon=True).start()
        return {"ok": True}

    def _launch_thread(self) -> None:
        try:
            self._play_thread()
        finally:
            self._game_process = None
            self._launch_busy = False

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
                authlib_cache_dir=self._authlib_cache_dir,
                api_client=self._api_client,
                launcher_name=APP_NAME,
                launcher_version=LAUNCHER_VERSION,
                reporter=reporter,
                debug_logger=debug_logger,
                already_installed=not wiped,
            )
            save_installed_profile(self._app_data_dir, profile)
            try:
                write_server_bookmark(
                    Path(self._minecraft_directory), APP_NAME, _server_address(profile)
                )
            except OSError as exc:
                # Без закладки игра всё равно зайдёт на сервер через quickPlay.
                debug_logger.log(f"Не удалось записать servers.dat: {exc!r}")
        except Exception as exc:  # noqa: BLE001 — репортим в UI любую причину провала
            debug_logger.log(f"ОШИБКА: {exc!r}")
            if reporter:
                reporter.status(f"Ошибка: {_describe_error(exc)}")
            return

        debug_logger.log("Запуск процесса игры…")
        if reporter:
            reporter.status("Запуск игры")
        self._game_killed = False
        try:
            self._game_process = subprocess.Popen(command, cwd=self._minecraft_directory)
        except OSError as exc:
            debug_logger.log(f"ОШИБКА запуска процесса: {exc!r}")
            if reporter:
                reporter.status(f"Ошибка: не удалось запустить игру: {exc}")
            return
        if reporter:
            reporter.game_state(True, "Игра запущена")

        # Поток и так фоновый — просто ждём выхода игры, чтобы UI вернул
        # кнопку PLAY и показал, как она завершилась.
        code = self._game_process.wait()
        debug_logger.log(f"Игра завершилась, код {code}, killed={self._game_killed}")
        if self._game_killed:
            message = "Игра остановлена"
        elif code == 0:
            message = "Игра закрыта"
        else:
            message = f"Игра завершилась с ошибкой (код {code})"
        self._game_process = None
        if reporter:
            reporter.game_state(False, message)
