# McLauncher2027 client

`core/` — вся бизнес-логика лаунчера, без UI-зависимостей. `ui_bridge/` — тонкий
мост в `pywebview.api`. `web/` — HTML/CSS/JS фронт. Смена дизайна (`web/`)
не требует трогать `core/`, пока сигнатуры методов `ui_bridge/api.py` не меняются
(см. `../DEV_PLAN.md`).

## Структура

- `loaders/` — установка/запуск Vanilla/Forge/Fabric/Quilt/NeoForge поверх
  `minecraft-launcher-lib` (реальный API библиотеки проверен инспекцией
  установленного пакета v8.0, а не по памяти/доке). `mod_loader_strategy.py`
  — единая обёртка для всех non-vanilla лоадеров через `mll.mod_loader`.
- `settings/` — локальный JSON-конфиг игрока (ник, RAM, разрешение, fullscreen,
  путь к Java, доп. JVM/game-аргументы, путь установки, включённые опциональные
  моды — **хранится только на клиенте**).
- `api_client/` — HTTP-клиент к `server/app/api/v1` (register/login/manifest).
- `sync/` — диффует манифест модов с бэка против локальной папки `mods/`:
  обязательные качаются всегда, опциональные — только включённые в settings,
  всё лишнее в папке удаляется.
- `launch/` — подмена `authlib-<версия>.jar` (см. ниже), сборка JVM/game-опций
  (`options_builder.py`, включая fullscreen/доп. аргументы/путь к Java) и
  `pipeline.py`, который связывает install лоадера -> sync модов -> patch
  authlib -> сборку launch-команды (`minecraft_launcher_lib.command.get_minecraft_command`)
  в одну функцию `prepare_and_get_launch_command`, которую дёргает `ui_bridge`.
- `ui_bridge/` — `LauncherApi` (контракт с `web/`: settings, регистрация/вход,
  опциональные моды, запуск игры в фоновом потоке) и `WebviewProgressReporter`
  (пушит статус/прогресс в UI через `window.evaluate_js`, т.к. `pywebview.api`
  — только запрос/ответ, без пуша от Python к JS).
- `web/` — `index.html`/`style.css`/`script.js`: экраны загрузки, входа/регистрации,
  главный экран с кнопкой "Играть", боковые панели настроек и опциональных модов.
  Тёмная тема, градиенты, анимации; иконки — свой набор inline SVG в CSS
  (не внешняя библиотека/CDN — нужно для офлайн сборки).
- `updater/app_updater.py` — отдельный маленький процесс самообновления,
  запускается лаунчером и закрывает его перед подменой файлов (см. ниже).

## Сборка

```bash
pip install -r requirements.txt
# лаунчер -> dist/McLauncher2027(.app) — см. точные флаги в
# .github/workflows/client-build.yml (разные для Windows/macOS: иконка,
# --windows-console-mode/--macos-create-app-bundle и т.п.)
python -m nuitka --standalone --output-dir=dist --include-data-dir=web=web \
  --include-data-dir=assets=assets --include-package-data=webview app.py
python -m nuitka --onefile --output-dir=dist --output-filename=app_updater \
  updater/app_updater.py
```

Сборка лаунчера — не onefile, а **standalone**: пивебвью грузит платформенные
бэкенды и JS-файлы динамически, `--include-package-data=webview` и явные
`--include-module=webview.platforms.*` обязательны, иначе на чистой машине
(CI) сборка запускается с пустым окном. Из-за standalone и на Windows, и на
macOS "лаунчер" — это папка (standalone-директория или `.app`-бандл), а не
один файл — см. `core/updater/paths.py`. `app_updater`
собирается отдельно и в архиве релиза кладётся **рядом** с папкой/бандлом
лаунчера, не внутри неё (иначе Windows не даст переименовать директорию, пока
внутри неё выполняется сам работающий `app_updater.exe`). Автоматизировано в
`.github/workflows/client-build.yml` (matrix Windows/macOS, ad-hoc `codesign`
на macOS против "повреждённого" Gatekeeper-вердикта, публикация в GitHub
Release при пуше тега).

## Запуск тестов

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

## Подмена authlib (не javaagent, а прямая замена файла)

Чтобы ванильный/Forge/Fabric клиент слал `hasJoined`/`join` на **наш** бэкенд,
а не на Mojang, стандартный `authlib-<версия>.jar` в
`libraries/com/mojang/authlib/` подменяется на версию с уже вбитым адресом
нашего сервера — тем же способом, каким это раньше делалось руками (найти
нужную версию authlib, поправить URL в hex/онлайн-редакторе, положить джар на
место оригинала). `core/launch/authlib_patch.py` автоматизирует последний шаг:

- `find_authlib_jars(minecraft_directory)` — какие версии authlib реально
  установлены после `loaders.install(...)`.
- `patch_authlib_jars(minecraft_directory, api_client, cache_dir)` — подменяет
  найденные файлы на `authlib-<версия>_skinfix.jar`, скачанный с бэкенда
  (`GET /api/v1/launcher/authlib-jars`) и закэшированный в `cache_dir`.
  Заготовки не зашиты в сборку — кладутся руками в `server/storage/authlib/`
  при подготовке бэкенда под конкретный сервер (см. ops-чеклист в
  `../DEV_PLAN.md`), обновляются независимо от релизов лаунчера.

Серверная сторона (замена authlib внутри `minecraft_server.jar`/Forge) —
ручная операция на самом игровом сервере, вне этого репозитория.
