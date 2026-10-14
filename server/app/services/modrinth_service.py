"""Поиск и установка модов с Modrinth (https://docs.modrinth.com/api/).

Моды ищутся и ставятся строго под текущий профиль сервера (загрузчик +
версия Minecraft). Скачанный jar проверяется по sha512 из ответа Modrinth и
дальше живёт как обычный загруженный вручную мод — лаунчеру источник не важен.
"""

import hashlib
import json

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_mod
from app.models.mod import Mod, ModType
from app.services import mod_service, profile_service
from app.services.errors import ServiceError

API_URL = "https://api.modrinth.com/v2"
# Modrinth просит осмысленный User-Agent, без него может резать по лимитам.
USER_AGENT = "McLauncher2027-admin (github.com/suntrackspb)"
# Защита от бесконечной цепочки зависимостей.
MAX_DEPENDENCIES = 20


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API_URL, timeout=30.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    )


async def _get_json(client: httpx.AsyncClient, path: str, **params):
    try:
        resp = await client.get(path, params=params or None)
    except httpx.HTTPError as exc:
        raise ServiceError(f"Modrinth недоступен: {exc}", error_code="MODRINTH") from exc
    if resp.status_code == 404:
        raise ServiceError("Мод не найден на Modrinth", error_code="NotFound")
    if resp.status_code != 200:
        raise ServiceError(f"Modrinth ответил {resp.status_code}", error_code="MODRINTH")
    return resp.json()


async def search(db: AsyncSession, query: str, limit: int = 20) -> list[dict]:
    profile = await profile_service.get_profile(db)
    facets = [
        ["project_type:mod"],
        [f"categories:{profile.loader.lower()}"],
        [f"versions:{profile.mc_version}"],
    ]
    async with _client() as client:
        data = await _get_json(
            client, "/search", query=query, limit=limit, facets=json.dumps(facets)
        )
    return [
        {
            "project_id": hit["project_id"],
            "slug": hit.get("slug"),
            "title": hit.get("title") or hit.get("slug"),
            "description": hit.get("description") or "",
            "icon_url": hit.get("icon_url"),
            "downloads": hit.get("downloads", 0),
            "client_side": hit.get("client_side"),
            "server_side": hit.get("server_side"),
        }
        for hit in data.get("hits", [])
    ]


async def _latest_version(client: httpx.AsyncClient, project_id: str, loader: str, mc_version: str) -> dict | None:
    versions = await _get_json(
        client,
        f"/project/{project_id}/version",
        loaders=json.dumps([loader.lower()]),
        game_versions=json.dumps([mc_version]),
    )
    # Modrinth отдаёт от новых к старым; релиз предпочтительнее беты.
    releases = [v for v in versions if v.get("version_type") == "release"]
    return (releases or versions or [None])[0]


def _primary_file(version: dict) -> dict:
    files = version.get("files") or []
    if not files:
        raise ServiceError("У версии мода нет файлов", error_code="MODRINTH")
    return next((f for f in files if f.get("primary")), files[0])


async def _download(client: httpx.AsyncClient, file: dict) -> bytes:
    try:
        resp = await client.get(file["url"])
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ServiceError(f"Не удалось скачать {file.get('filename')}: {exc}", error_code="MODRINTH") from exc
    expected = (file.get("hashes") or {}).get("sha512")
    if expected and hashlib.sha512(resp.content).hexdigest() != expected:
        raise ServiceError(f"Хеш {file.get('filename')} не совпал — файл повреждён", error_code="MODRINTH")
    return resp.content


async def install(db: AsyncSession, project_id: str, mod_type: ModType) -> dict:
    """Ставит мод и его обязательные зависимости. Возвращает
    {"installed": [Mod...], "skipped": [имена уже стоящих]}."""
    profile = await profile_service.get_profile(db)
    loader, mc_version = profile.loader.lower(), profile.mc_version

    existing = await crud_mod.get_all(db)
    known_hashes = {(m.file_hash, m.loader.lower(), m.mc_version) for m in existing}

    installed: list[Mod] = []
    skipped: list[str] = []
    seen: set[str] = set()
    queue: list[tuple[str, ModType]] = [(project_id, mod_type)]

    async with _client() as client:
        while queue:
            pid, kind = queue.pop(0)
            if pid in seen:
                continue
            seen.add(pid)
            if len(seen) > MAX_DEPENDENCIES:
                raise ServiceError("Слишком много зависимостей", error_code="MODRINTH")

            project = await _get_json(client, f"/project/{pid}")
            version = await _latest_version(client, pid, loader, mc_version)
            if version is None:
                if pid == project_id:
                    raise ServiceError(
                        f"У «{project.get('title')}» нет версии под {loader} {mc_version}",
                        error_code="NotFound",
                    )
                raise ServiceError(
                    f"Зависимость «{project.get('title')}» не найдена под {loader} {mc_version} — добавьте её вручную",
                    error_code="NotFound",
                )

            file = _primary_file(version)
            content = await _download(client, file)
            file_hash = hashlib.sha256(content).hexdigest()
            if (file_hash, loader, mc_version) in known_hashes:
                skipped.append(project.get("title") or pid)
            else:
                mod = await mod_service.upload_mod(
                    db,
                    name=project.get("title") or file["filename"],
                    description=(project.get("description") or "")[:512] or None,
                    file_name=file["filename"],
                    mod_type=kind,
                    loader=loader,
                    mc_version=mc_version,
                    content=content,
                    # Modrinth знает, нужен ли мод серверу: "unsupported" —
                    # чисто клиентский, на сервер его не заливаем.
                    server_side=project.get("server_side") != "unsupported",
                    modrinth_project_id=pid,
                )
                known_hashes.add((file_hash, loader, mc_version))
                installed.append(mod)

            # Обязательная зависимость нужна всем, у кого стоит мод: для
            # обязательного мода — тоже обязательная, для опционального —
            # опциональная (игрок включает их вместе).
            for dep in version.get("dependencies") or []:
                if dep.get("dependency_type") == "required" and dep.get("project_id"):
                    queue.append((dep["project_id"], kind))

    return {"installed": installed, "skipped": skipped}

