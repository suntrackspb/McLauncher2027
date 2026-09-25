import json


class WebviewProgressReporter:
    """Реализация ProgressReporter поверх pywebview: пушит статус/прогресс в JS
    через evaluate_js, потому что pywebview.api — это только request/response,
    а установка идёт в фоновом потоке (см. LauncherApi.play)."""

    def __init__(self, window):
        self._window = window

    def status(self, message: str) -> None:
        self._window.evaluate_js(f"window.onLauncherStatus({json.dumps(message)})")

    def progress(self, current: int, maximum: int) -> None:
        self._window.evaluate_js(f"window.onLauncherProgress({current}, {maximum})")
