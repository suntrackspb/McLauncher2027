from abc import ABC, abstractmethod
from typing import Protocol


class ProgressReporter(Protocol):
    """Мост в UI. `core` ничего не знает про pywebview — просто дёргает эти методы,
    ui_bridge сам решает, как показать прогресс-бар/статус во фронте."""

    def status(self, message: str) -> None: ...
    def progress(self, current: int, maximum: int) -> None: ...


# Этапы, которые minecraft-launcher-lib объявляет через setStatus, — по-русски.
STAGE_NAMES = {
    "Download Libraries": "Загрузка библиотек",
    "Download Assets": "Загрузка ресурсов игры",
    "Install java runtime": "Установка Java",
    "Installation complete": "Установка завершена",
}


def to_callback_dict(reporter: ProgressReporter | None) -> dict:
    """Адаптер ProgressReporter -> CallbackDict, который ждёт minecraft-launcher-lib.

    Библиотека зовёт setStatus("Download <файл>") на каждый файл из рабочих
    потоков — это тысячи синхронных evaluate_js, которые забивают WebView и
    не дают дойти прогрессу. Поэтому пофайловые статусы глушим, а прогресс
    отдаём только при смене целого процента."""
    if reporter is None:
        return {}

    state = {"max": 0, "percent": -1}

    def set_max(value: int) -> None:
        state["max"] = value
        state["percent"] = -1

    def set_progress(value: int) -> None:
        maximum = state["max"]
        if maximum <= 0:
            reporter.progress(value, maximum)
            return
        percent = min(100, value * 100 // maximum)
        if percent != state["percent"]:
            state["percent"] = percent
            reporter.progress(value, maximum)

    def set_status(value: str) -> None:
        if value in STAGE_NAMES:
            reporter.status(STAGE_NAMES[value])
        elif not value.startswith("Download "):
            reporter.status(value)

    return {"setStatus": set_status, "setProgress": set_progress, "setMax": set_max}


class LoaderStrategy(ABC):
    """Единый интерфейс установки/проверки конкретного мод-лоадера
    (vanilla/forge/fabric/quilt/neoforge). Реализации — тонкие адаптеры над
    minecraft-launcher-lib, вся хитрая логика (classpath, скачивание установщиков,
    JSON версий) остаётся в самой библиотеке."""

    name: str

    @abstractmethod
    def install(
        self,
        minecraft_directory: str,
        mc_version: str,
        loader_version: str | None = None,
        reporter: ProgressReporter | None = None,
    ) -> str:
        """Устанавливает (или доустанавливает недостающее) и возвращает version_id,
        который нужно передать в minecraft_launcher_lib.command.get_minecraft_command."""

    @abstractmethod
    def is_installed(
        self, minecraft_directory: str, mc_version: str, loader_version: str | None = None
    ) -> bool:
        """Проверка без сети — используется, чтобы не переустанавливать при каждом запуске."""

    @abstractmethod
    def resolve_version_id(
        self, minecraft_directory: str, mc_version: str, loader_version: str | None = None
    ) -> str:
        """version_id, под которым лоадер будет установлен, без выполнения установки."""
