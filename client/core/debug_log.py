import json
import sys
import time
from pathlib import Path

DEBUG_LOG_FILENAME = "debug.log"


def is_debug_flag_set() -> bool:
    """Проверяет флаг командной строки `--debug` (например, для запуска
    собранного .exe/.app из терминала без включения галочки в настройках)."""
    return "--debug" in sys.argv


def debug_log_path() -> Path:
    """Файл лога кладём рядом с исполняемым файлом (а не в AppData/Library —
    там его сложнее найти игроку), чтобы можно было просто попросить прислать
    файл из той же папки, где лежит лаунчер."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / DEBUG_LOG_FILENAME


class DebugLogger:
    """Подробный лог одного запуска игры: с какими итоговыми параметрами
    (профиль, JVM-аргументы, финальная команда) лаунчер пытается запустить
    Minecraft — чтобы по присланному файлу можно было понять, на каком именно
    шаге что-то пошло не так. Пишется только когда включён debug-режим
    (галочка в настройках или флаг --debug) — по умолчанию лаунчер этот файл
    не создаёт и не трогает."""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._path = debug_log_path() if enabled else None
        if self._path:
            # Новый лог на каждый запуск — не накапливаем историю прошлых сессий.
            try:
                self._path.write_text("", encoding="utf-8")
            except OSError:
                self.enabled = False
                self._path = None

    def log(self, message: str) -> None:
        if not self.enabled:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass

    def log_block(self, title: str, data) -> None:
        """Логирует заголовок этапа + структурированные данные (dict/list) под
        ним в читаемом JSON — используется для итоговых наборов параметров
        (options, команда запуска, план синхронизации модов и т.п.)."""
        if not self.enabled:
            return
        self.log(f"{title}:")
        self.log(json.dumps(data, ensure_ascii=False, indent=2, default=str))
