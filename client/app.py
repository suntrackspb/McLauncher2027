from pathlib import Path

import webview

from ui_bridge.api import LauncherApi
from ui_bridge.config import APP_NAME, WINDOW_HEIGHT, WINDOW_WIDTH

WEB_DIR = Path(__file__).resolve().parent / "web"


def main() -> None:
    api = LauncherApi()
    window = webview.create_window(
        APP_NAME,
        str(WEB_DIR / "index.html"),
        js_api=api,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        resizable=False,
        background_color="#0f1117",
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
