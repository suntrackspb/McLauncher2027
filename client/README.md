# McLauncher2027 client — core

`core/` — вся бизнес-логика лаунчера, без UI-зависимостей (pywebview подключается
позже отдельным тонким слоем `ui_bridge/`, см. `../DEV_PLAN.md`).

## Структура

- `loaders/` — установка/запуск Vanilla/Forge/Fabric/Quilt/NeoForge поверх
  `minecraft-launcher-lib` (реальный API библиотеки проверен инспекцией
  установленного пакета v8.0, а не по памяти/доке). `mod_loader_strategy.py`
  — единая обёртка для всех non-vanilla лоадеров через `mll.mod_loader`.
- `settings/` — локальный JSON-конфиг игрока (ник, RAM, разрешение, путь
  установки, включённые опциональные моды — **хранится только на клиенте**).
- `api_client/` — HTTP-клиент к `server/app/api/v1` (register/login/manifest).
- `sync/` — диффует манифест модов с бэка против локальной папки `mods/`:
  обязательные качаются всегда, опциональные — только включённые в settings,
  всё лишнее в папке удаляется.
- `launch/` — подмена `authlib-<версия>.jar` (см. ниже) + `pipeline.py`,
  который связывает install лоадера -> sync модов -> patch authlib -> сборку
  launch-команды (`minecraft_launcher_lib.command.get_minecraft_command`) в
  одну функцию `prepare_and_get_launch_command`, которую дёргает `ui_bridge`.

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
