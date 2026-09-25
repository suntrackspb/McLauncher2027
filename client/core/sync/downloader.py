import hashlib
from pathlib import Path

import requests

from core.loaders.base import ProgressReporter
from core.sync.mod_sync import ModEntry, SyncPlan


class DownloadIntegrityError(Exception):
    """sha256 скачанного файла не совпал с манифестом — качаем не то, что думали."""


def apply_sync_plan(
    plan: SyncPlan,
    mods_dir: Path,
    reporter: ProgressReporter | None = None,
    session: requests.Session | None = None,
) -> None:
    mods_dir.mkdir(parents=True, exist_ok=True)
    session = session or requests.Session()

    total = len(plan.to_download)
    for index, entry in enumerate(plan.to_download, start=1):
        if reporter:
            reporter.status(f"Скачивание {entry.name} ({index}/{total})")
        _download_one(entry, mods_dir / entry.file_name, session, reporter)

    for path in plan.to_delete:
        path.unlink(missing_ok=True)


def _download_one(
    entry: ModEntry, dest: Path, session: requests.Session, reporter: ProgressReporter | None
) -> None:
    tmp_path = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()

    with session.get(entry.url, stream=True, timeout=30) as resp:
        resp.raise_for_status()
        downloaded = 0
        with tmp_path.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if reporter:
                    reporter.progress(downloaded, entry.size)

    if digest.hexdigest() != entry.file_hash:
        tmp_path.unlink(missing_ok=True)
        raise DownloadIntegrityError(
            f"Хеш {entry.file_name} не совпал с манифестом — скачивание повреждено или подменено"
        )

    tmp_path.replace(dest)
