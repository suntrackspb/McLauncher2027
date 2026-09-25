# -*- mode: python ; coding: utf-8 -*-
"""Спецификация сборки лаунчера для macOS и Windows (onedir, не onefile —
надёжнее для pywebview: onefile распаковывает себя во временную папку при
каждом запуске, а pywebview и так везёт свои платформенные бэкенды/JS-файлы,
которые должны просто лежать рядом, без лишней распаковки).

Запуск:  pyinstaller --noconfirm --clean build.spec
"""

import sys

from PyInstaller.utils.hooks import collect_all, copy_metadata

APP_NAME = "McLauncher2027"
BUNDLE_ID = "ru.spbwar.mclauncher2027"

datas = [("web", "web"), ("assets", "assets")]
binaries = []
hiddenimports = []


def _collect(package):
    """Забрать пакет целиком: data-файлы, бинарники и динамические импорты."""
    global datas, binaries, hiddenimports
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden


# pywebview грузит платформенные бэкенды динамически и везёт свои
# webview/lib/js/*.js — без collect_all анализатор PyInstaller их не видит,
# и собранный на чистой машине (CI) лаунчер падает в рантайме с пустым окном.
_collect("webview")
datas += copy_metadata("pywebview")

if sys.platform == "win32":
    # WebView2-бэкенд pywebview идёт через pythonnet/clr_loader.
    _collect("clr_loader")
    _collect("pythonnet")
    hiddenimports += [
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
    ]
    icon = None
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
    icon = None
else:
    hiddenimports += ["webview.platforms.gtk"]
    icon = None

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": "McLauncher2027",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.games",
        },
    )
