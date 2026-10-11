import struct

from core.textures import check_texture

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png(width: int, height: int) -> bytes:
    ihdr = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4


def test_valid_skins():
    assert check_texture("skin", png(64, 64)) is None
    assert check_texture("skin", png(64, 32)) is None
    assert check_texture("skin", png(128, 128)) is None


def test_valid_capes():
    assert check_texture("cape", png(64, 32)) is None
    assert check_texture("cape", png(22, 17)) is None


def test_rejects_not_png():
    assert check_texture("skin", b"GIF89a" + b"\x00" * 30) == "Файл должен быть PNG"


def test_rejects_wrong_size():
    assert "64x64 или 64x32" in check_texture("skin", png(100, 100))
    assert "64x32" in check_texture("cape", png(64, 64))


def test_rejects_too_big_file():
    assert "слишком большой" in check_texture("skin", png(64, 64) + b"\x00" * (1024 * 1024))
