import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModEntry:
    id: int
    name: str
    file_name: str
    url: str
    file_hash: str
    size: int


@dataclass
class SyncPlan:
    to_download: list[ModEntry]
    to_delete: list[Path]


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_hashes(mods_dir: Path) -> dict[str, str]:
    if not mods_dir.exists():
        return {}
    return {p.name: _sha256_of(p) for p in mods_dir.iterdir() if p.is_file()}


def plan_sync(
    required: list[dict],
    optional: list[dict],
    enabled_optional_mod_ids: set[int],
    mods_dir: Path,
) -> SyncPlan:
    """Обязательные моды нужны всегда. Опциональные — только те, что игрок сам
    включил (id из local settings). Всё остальное в mods/ считается мусором и
    удаляется (снятая обязательная зависимость, отключённый опциональный мод)."""
    wanted: dict[str, ModEntry] = {}

    for raw in required:
        entry = ModEntry(**{k: raw[k] for k in ("id", "name", "file_name", "url", "file_hash", "size")})
        wanted[entry.file_name] = entry

    for raw in optional:
        if raw["id"] not in enabled_optional_mod_ids:
            continue
        entry = ModEntry(**{k: raw[k] for k in ("id", "name", "file_name", "url", "file_hash", "size")})
        wanted[entry.file_name] = entry

    local_hashes = _local_hashes(mods_dir)

    to_download = [
        entry for entry in wanted.values() if local_hashes.get(entry.file_name) != entry.file_hash
    ]
    to_delete = [mods_dir / file_name for file_name in local_hashes if file_name not in wanted]

    return SyncPlan(to_download=to_download, to_delete=to_delete)
