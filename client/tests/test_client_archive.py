from zipfile import ZipFile

import pytest

from core.launch import client_archive


def _serve_zip(monkeypatch, files):
    def download(_url, destination, _reporter):
        with ZipFile(destination, "w") as archive:
            for name, contents in files.items():
                archive.writestr(name, contents)

    monkeypatch.setattr(client_archive, "_download", download)


@pytest.mark.parametrize("prefix", ["", "Minecraft/"])
def test_install_unpacks_game_and_reuses_the_existing_copy(monkeypatch, tmp_path, prefix):
    game = tmp_path / "instance" / "minecraft"
    files = {f"{prefix}mods/example.jar": "jar", f"{prefix}config/example.json": "{}"}
    _serve_zip(monkeypatch, files)

    client_archive.install_client_archive("https://example.test/pack.zip", game)
    assert (game / "mods/example.jar").read_text() == "jar"
    assert (game / "config/example.json").read_text() == "{}"

    files[f"{prefix}mods/example.jar"] = "new jar"
    client_archive.install_client_archive("https://example.test/pack.zip", game)
    assert (game / "mods/example.jar").read_text() == "jar"


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
