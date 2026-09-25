from pathlib import Path

import webview

from ui_bridge.api import LauncherApi

WEB_DIR = Path(__file__).resolve().parent / "web"


def main() -> None:
    api = LauncherApi()
    window = webview.create_window(
        "McLauncher2027",
        str(WEB_DIR / "index.html"),
        js_api=api,
        width=1000,
        height=650,
        resizable=False,
        background_color="#0f1117",
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
