from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_mod
from app.models.mod import Mod, ModType
from app.services import mod_storage
from app.services.errors import ServiceError


async def get_required_mods(db: AsyncSession, loader: str, mc_version: str) -> list[Mod]:
    return await crud_mod.get_by_filter(
        db, mod_type=ModType.required, loader=loader, mc_version=mc_version
    )


async def get_optional_mods(db: AsyncSession, loader: str, mc_version: str) -> list[Mod]:
    return await crud_mod.get_by_filter(
        db, mod_type=ModType.optional, loader=loader, mc_version=mc_version
    )


async def list_all_mods(db: AsyncSession) -> list[Mod]:
    return await crud_mod.get_all(db)


async def upload_mod(
    db: AsyncSession,
    *,
    name: str,
    description: str | None,
    file_name: str,
    mod_type: ModType,
    loader: str,
    mc_version: str,
    content: bytes,
) -> Mod:
    file_hash, size = mod_storage.save_mod_file(content)
    return await crud_mod.create(
        db,
        name=name,
        description=description,
        file_name=file_name,
        url=mod_storage.mod_url(file_hash),
        file_hash=file_hash,
        size=size,
        mod_type=mod_type,
        loader=loader,
        mc_version=mc_version,
    )


async def delete_mod(db: AsyncSession, mod_id: int) -> None:
    mod = await crud_mod.get_by_id(db, mod_id)
    if not mod:
        raise ServiceError("Мод не найден", error_code="NotFound")
    file_hash = mod.file_hash
    await crud_mod.delete(db, mod)
    # один и тот же jar могут использовать несколько записей (хеш = имя файла)
    if await crud_mod.count_by_hash(db, file_hash) == 0:
        mod_storage.delete_mod_file(file_hash)


async def update_mod(db: AsyncSession, mod_id: int, **fields) -> Mod:
    mod = await crud_mod.get_by_id(db, mod_id)
    if not mod:
        raise ServiceError("Мод не найден", error_code="NotFound")
    if "name" in fields and not (fields["name"] or "").strip():
        raise ServiceError("Название не может быть пустым", error_code="BadRequest")
    return await crud_mod.update(db, mod, **fields)
