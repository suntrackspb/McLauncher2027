"""Приведение файлов игрового сервера к профилю: моды и authlib.

Работает поверх RemoteFS (FTP или SFTP — без разницы), синхронно.
sync(apply=False) — только план, что будет сделано; apply=True — делает.
Ничего не удаляет: лишние моды и оригинальный authlib уходят в бэкап.
"""

import hashlib
import json
import posixpath
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.services import authlib_service, mod_storage
from app.services.remote_fs import RemoteError, RemoteFS

MODS_DIR = "mods"
REMOVED_DIR = "mods_removed"
AUTHLIB_DIR = "libraries/com/mojang/authlib"


@dataclass
class ModToSync:
    file_name: str
    file_hash: str
    size: int


@dataclass
class SyncReport:
    mods_upload: list[str] = field(default_factory=list)
    mods_ok: list[str] = field(default_factory=list)
    mods_remove: list[str] = field(default_factory=list)
    # версия -> patched / to_patch / no_patch
    authlib: dict[str, str] = field(default_factory=dict)
    authlib_found: bool = True
    applied: bool = False
    backup_dir: str | None = None
    # Отпечаток плана: POST применяет только тот план, что админ видел.
    plan_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _jar_files(fs: RemoteFS, path: str) -> dict[str, int]:
    try:
        return {e.name: e.size for e in fs.list_dir(path) if not e.is_dir and e.name.endswith(".jar")}
    except RemoteError:
        return {}  # папки ещё нет


class PlanChanged(Exception):
    pass


def _plan_id(report: SyncReport) -> str:
    data = json.dumps([report.mods_upload, report.mods_remove, report.authlib], sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def sync(
    fs: RemoteFS,
    mods: list[ModToSync],
    *,
    apply: bool,
    sync_mods: bool = True,
    expected_plan_id: str | None = None,
) -> SyncReport:
    report = SyncReport(applied=apply)

    if sync_mods:
        remote = _jar_files(fs, MODS_DIR)
        wanted = {m.file_name: m for m in mods}
        for name, mod in sorted(wanted.items()):
            (report.mods_ok if remote.get(name) == mod.size else report.mods_upload).append(name)
        report.mods_remove = sorted(set(remote) - set(wanted))

    try:
        versions = sorted(e.name for e in fs.list_dir(AUTHLIB_DIR) if e.is_dir)
    except RemoteError:
        versions = []
    report.authlib_found = bool(versions)
    originals: dict[str, bytes] = {}
    for version in versions:
        patched = authlib_service.patched_jar(version)
        if patched is None:
            report.authlib[version] = "no_patch"
            continue
        path = posixpath.join(AUTHLIB_DIR, version, f"authlib-{version}.jar")
        try:
            current = fs.read(path)
        except RemoteError:
            current = b""
        report.authlib[version] = "patched" if current == patched else "to_patch"
        originals[version] = current

    report.plan_id = _plan_id(report)
    if not apply:
        return report
    if expected_plan_id and expected_plan_id != report.plan_id:
        raise PlanChanged()

    if report.mods_remove:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        report.backup_dir = posixpath.join(REMOVED_DIR, stamp)
        fs.mkdirs(report.backup_dir)
        for name in report.mods_remove:
            fs.rename(posixpath.join(MODS_DIR, name), posixpath.join(report.backup_dir, name))
    if report.mods_upload:
        fs.mkdirs(MODS_DIR)
        wanted = {m.file_name: m for m in mods}
        for name in report.mods_upload:
            fs.write(posixpath.join(MODS_DIR, name), mod_storage.read_mod_file(wanted[name].file_hash))

    for version, state in report.authlib.items():
        if state != "to_patch":
            continue
        base = posixpath.join(AUTHLIB_DIR, version, f"authlib-{version}.jar")
        # Оригинал сохраняем один раз — повторный патч не затрёт его патченым.
        if originals[version] and not fs.exists(base + ".orig"):
            fs.write(base + ".orig", originals[version])
        fs.write(base, authlib_service.patched_jar(version))
        report.authlib[version] = "patched"
    return report
