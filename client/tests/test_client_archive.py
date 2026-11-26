from contextlib import nullcontext
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from core.launch import client_archive


def _serve_zip(monkeypatch, files, *, checksum=None):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    payload = buffer.getvalue()
    if checksum is None:
        checksum = f"{sha256(payload).hexdigest().upper()}  pack.zip\n".encode("ascii")

    calls = []

    def get(url, *, stream, timeout):
        calls.append(url)
        data = checksum if ".zip.sha256" in url else payload
        return nullcontext(SimpleNamespace(
            headers={"Content-Length": str(len(data))},
            raise_for_status=lambda: None,
            iter_content=lambda *, chunk_size: (data[:32], data[32:]),
        ))

    monkeypatch.setattr(client_archive.requests, "get", get)
    return calls


@pytest.mark.parametrize("prefix", ["", "Minecraft/"])
def test_install_unpacks_game_and_reuses_the_existing_copy(monkeypatch, tmp_path, prefix):
    game = tmp_path / "instance" / "minecraft"
    files = {f"{prefix}mods/example.jar": "jar", f"{prefix}config/example.json": "{}"}
    calls = _serve_zip(monkeypatch, files)

    url = "https://example.test/pack.zip?version=1"
    client_archive.install_client_archive(url, game)
    assert (game / "mods/example.jar").read_text() == "jar"
    assert (game / "config/example.json").read_text() == "{}"

    client_archive.install_client_archive(url, game)
    assert (game / "mods/example.jar").read_text() == "jar"
    assert calls == ["https://example.test/pack.zip.sha256?version=1", url]


def test_checksum_mismatch_rejects_download_before_extraction(mocker, monkeypatch, tmp_path):
    game = tmp_path / "instance" / "minecraft"
    game.mkdir(parents=True)
    (game / "options.txt").write_text("current settings")
    _serve_zip(monkeypatch, {"mods/example.jar": "jar"}, checksum=b"0" * 64)
    extract = mocker.patch.object(client_archive, "_extract")

    with pytest.raises(client_archive.ClientArchiveError, match="SHA-256.*не совпал"):
        client_archive.install_client_archive("https://example.test/pack.zip", game, force=True)

    extract.assert_not_called()
    assert (game / "options.txt").read_text() == "current settings"
    assert sorted(game.parent.iterdir()) == [game]


def test_bad_checksum_prevents_archive_download(monkeypatch, tmp_path):
    calls = _serve_zip(monkeypatch, {"mods/example.jar": "jar"}, checksum=b"not a checksum")

    with pytest.raises(client_archive.ClientArchiveError, match="Некорректная контрольная сумма"):
        client_archive.install_client_archive("https://example.test/pack.zip", tmp_path / "minecraft")

    assert calls == ["https://example.test/pack.zip.sha256"]


def test_invalid_zip_cannot_replace_the_existing_game(monkeypatch, tmp_path):
    game = tmp_path / "instance" / "minecraft"
    game.mkdir(parents=True)
    (game / "options.txt").write_text("current settings")
    _serve_zip(monkeypatch, {"mods/example.jar": "jar", "../outside.txt": "outside"})

    with pytest.raises(client_archive.ClientArchiveError):
        client_archive.install_client_archive("https://example.test/pack.zip", game, force=True)

    assert (game / "options.txt").read_text() == "current settings"
    assert sorted(game.parent.iterdir()) == [game]


def test_reinstall_keeps_a_copy_of_the_previous_game(monkeypatch, tmp_path):
    game = tmp_path / "instance" / "minecraft"
    game.mkdir(parents=True)
    (game / "options.txt").write_text("current settings")
    _serve_zip(monkeypatch, {"mods/example.jar": "jar"})

    client_archive.install_client_archive("https://example.test/pack.zip", game, force=True)

    assert (game / "mods/example.jar").exists()
    previous, = game.parent.glob("previous-*")
    assert (previous / "options.txt").read_text() == "current settings"
