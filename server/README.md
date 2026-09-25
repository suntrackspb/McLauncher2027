# McLauncher2027 backend

FastAPI-бэкенд лаунчера: свои аккаунты (bcrypt) + Yggdrasil-совместимая сессия
(`hasJoined`/`join`/`profile`) для скинов, плюс манифест обязательных/опциональных модов.

Поведение `session`-эндпоинтов сверено с рабочей PHP-версией
(`older_projects/authlib_skinfix_by_TaoGunner-2`), но без её проблем — bcrypt вместо
MD5, параметризованные запросы через SQLAlchemy ORM вместо конкатенации строк.

## Запуск для разработки

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

## Тесты

```bash
python -m pytest -q
```

## Продакшен

```bash
docker compose up --build
```

## Эндпоинты (v1)

- `POST /api/v1/auth/register` / `POST /api/v1/auth/login`
- `GET /api/v1/hasJoined`, `POST /api/v1/join`, `GET /api/v1/profile` — Yggdrasil-сессия
- `GET /api/v1/mods/manifest` — обязательные моды (`loader`, `mc_version`)
- `GET /api/v1/mods/optional` — каталог опциональных модов
- `POST /api/v1/players/me/skin`, `.../cape` — загрузка скина/плаща (multipart:
  `uuid`+`access_token`+`file`), отдаются через `/textures/{skin|cape}/{hash}.png`
- `POST /api/v1/admin/login` — пароль → JWT (12ч); `GET/POST /api/v1/admin/mods`,
  `DELETE /api/v1/admin/mods/{id}` — управление списком модов (Bearer-токен),
  загруженные jar-файлы отдаются через `/mod-files/{hash}.jar`. Пароль
  администратора — `ADMIN_PASSWORD` в `.env`, либо генерируется при первом
  запуске и печатается в консоль (см. `app/core/admin_auth.py`)

Полная OpenAPI-схема — на `/docs` после запуска.

## Пока не реализовано (см. `../DEV_PLAN.md`)

- Хранение и отдача скинов/плащей (сейчас `textures` в профиле всегда пустой).
