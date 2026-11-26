"""Install a ready-to-play ZIP into a directory managed by the launcher."""

import hashlib
import json
import re
import shutil
import stat
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

import requests

from core.launch.options_builder import ServerProfile
from core.loaders.base import ProgressReporter

_GAME_ENTRIES = {
    "mods", "config", "defaultconfigs", "kubejs", "scripts", "resourcepacks",
    "shaderpacks", "versions", "options.txt",
}
_CHUNK_SIZE = 256 * 1024
_MAX_CHECKSUM_BYTES = 4096


class ClientArchiveError(Exception):
    pass


def archive_game_directory(app_data: Path, profile: ServerProfile) -> Path:
    identity = json.dumps([
        profile.client_zip_url, profile.mc_version, profile.loader, profile.loader_version,
    ])
    key = hashlib.sha256(identity.encode()).hexdigest()[:24]
    return app_data / "client-archives" / key / "minecraft"


def _expected_sha256(url: str) -> str:
    parts = urlsplit(url)
    checksum_url = parts._replace(path=f"{parts.path}.sha256", fragment="").geturl()
    data = bytearray()
    try:
        with requests.get(checksum_url, stream=True, timeout=(10, 30)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024):
                data.extend(chunk)
                if len(data) > _MAX_CHECKSUM_BYTES:
                    raise ClientArchiveError("Файл SHA-256 клиентского ZIP слишком большой")
    except requests.RequestException as exc:
        raise ClientArchiveError("Не удалось скачать файл SHA-256 клиентского ZIP") from exc

    fields = data.split(maxsplit=1)
    if not fields or not re.fullmatch(rb"[0-9a-fA-F]{64}", fields[0]):
        raise ClientArchiveError("Некорректная контрольная сумма SHA-256 клиентского ZIP")
    return fields[0].decode("ascii").lower()


def _download(url: str, archive: Path, reporter: ProgressReporter | None) -> str:
    if reporter:
        reporter.status("Скачивание клиентской сборки")
    digest = hashlib.sha256()
    try:
        with requests.get(url, stream=True, timeout=(10, 60)) as response:
            response.raise_for_status()
            length = response.headers.get("Content-Length", "")
            total = int(length) if length.isascii() and length.isdecimal() else 0
            downloaded = 0
            with archive.open("wb") as target:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    target.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    if reporter and total:
                        reporter.progress(downloaded, total)
    except requests.RequestException as exc:
        status = exc.response.status_code if exc.response is not None else None
        detail = f" (HTTP {status})" if status else ""
        raise ClientArchiveError(f"Не удалось скачать клиентский ZIP{detail}") from exc
    return digest.hexdigest()


def _extract(archive: Path, staging: Path) -> Path:
    try:
        with ZipFile(archive) as source:
            for entry in source.infolist():
                name = entry.orig_filename
                parts = name.removesuffix("/").split("/")
                kind = stat.S_IFMT(entry.external_attr >> 16)
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or any(
                    part in {"", ".", ".."}
                    or part.endswith((".", " "))
                    or any(char in '\\:<>"|?*' or ord(char) < 32 for char in part)
                    or PureWindowsPath(part).is_reserved()
                    for part in parts
                ):
                    raise ClientArchiveError("В ZIP есть недопустимый путь или специальный файл")
                if parts[0] == "__MACOSX" or parts[-1] == ".DS_Store":
                    continue
                target = staging.joinpath(*parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(entry) as data, target.open("xb") as output:
                        shutil.copyfileobj(data, output, length=_CHUNK_SIZE)
    except (BadZipFile, RuntimeError, FileExistsError, NotADirectoryError, IsADirectoryError) as exc:
        raise ClientArchiveError("Не удалось распаковать клиентский ZIP") from exc

    entries = list(staging.iterdir())
    if any(entry.name in _GAME_ENTRIES for entry in entries):
        return staging
    if len(entries) == 1 and entries[0].is_dir():
        wrapper = entries[0]
        if any(entry.name in _GAME_ENTRIES for entry in wrapper.iterdir()):
            return wrapper

    raise ClientArchiveError("ZIP должен содержать папку игры с файлами сборки, например mods и config")


def install_client_archive(
    url: str, game_directory: Path, reporter: ProgressReporter | None = None, *, force: bool = False,
) -> None:
    if game_directory.is_dir() and not force:
        return

    parent = game_directory.parent
    parent.mkdir(parents=True, exist_ok=True)
    if reporter:
        reporter.status("Получение контрольной суммы сборки")
    expected = _expected_sha256(url)
    with TemporaryDirectory(prefix=".install-", dir=parent) as tmp:
        archive = Path(tmp) / "client.zip"
        if _download(url, archive, reporter) != expected:
            raise ClientArchiveError("SHA-256 клиентского ZIP не совпал. Попробуйте скачать сборку заново.")

        staging = Path(tmp) / "unpacked"
        staging.mkdir()
        if reporter:
            reporter.status("Распаковка клиентской сборки")
        game = _extract(archive, staging)

        if not force and game_directory.is_dir():
            return

        previous = None
        if force and game_directory.exists():
            previous = parent / f"previous-{uuid4().hex}"
            game_directory.rename(previous)
        try:
            game.rename(game_directory)
        except OSError:
            if previous is not None and not game_directory.exists():
                previous.rename(game_directory)
            elif previous is None and not force and game_directory.is_dir():
                return
            raise
