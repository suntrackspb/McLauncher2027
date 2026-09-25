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
  (не внешняя библиотека/CDN — нужно для офлайн PyInstaller-сборки).
- `updater/app_updater.py` — отдельный маленький процесс самообновления,
  запускается лаунчером и закрывает его перед подменой файлов (см. ниже).

## Сборка

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean build.spec        # лаунчер -> dist/McLauncher2027(.app)
pyinstaller updater/app_updater.py --name app_updater --onefile --noconfirm
```

`build.spec` — не onefile, а **onedir**: пивебвью грузит платформенные бэкенды и
JS-файлы динамически, `collect_all("webview")` + `copy_metadata("pywebview")`
обязательны, иначе на чистой машине (CI) сборка запускается с пустым окном.
Из-за onedir и на Windows, и на macOS "лаунчер" — это папка (onedir-директория
или `.app`-бандл), а не один файл — см. `core/updater/paths.py`. `app_updater`
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
- `patch_authlib_jars(minecraft_directory, patched_jars_dir)` — подменяет
  найденные файлы на `authlib-<версия>_skinfix.jar` из `patched_jars_dir`
  (заготовки кладём в `client/assets/authlib_patched/`, готовятся один раз при
  подготовке сборки под конкретный бэкенд — см. ops-чеклист в `../DEV_PLAN.md`).

Серверная сторона (замена authlib внутри `minecraft_server.jar`/Forge) —
ручная операция на самом игровом сервере, вне этого репозитория.
