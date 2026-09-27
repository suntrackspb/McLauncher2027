# Перезаписывается в CI шагом "Set launcher version" из git-тега (v1.0.x)
# перед сборкой релиза — руками эту версию больше не проставляем (см.
# ui_bridge/config.py и .github/workflows/client-build.yml). Значение ниже
# используется только при локальном запуске из исходников/workflow_dispatch
# без тега, где нет реального релиза для сравнения.
LAUNCHER_VERSION = "v0.0.0-dev"
