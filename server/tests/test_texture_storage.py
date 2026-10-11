import struct
import pytest

from app.core.config import settings
from app.services import texture_storage
from app.services.errors import ServiceError

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def _png(width: int, height: int) -> bytes:
    """Минимальный PNG: сигнатура + IHDR — сервер смотрит только на них."""
    ihdr = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return PNG_HEADER + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00\x00\x00\x00" + b"fake-content"


FAKE_PNG = _png(64, 64)
FAKE_CAPE = _png(64, 32)


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "textures_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "public_base_url", "http://test.local")


def test_save_texture_accepts_png_and_returns_hash():
    file_hash = texture_storage.save_texture("skin", FAKE_PNG)
    assert len(file_hash) == 32
    saved = texture_storage._storage_dir("skin") / f"{file_hash}.png"
    assert saved.read_bytes() == FAKE_PNG


def test_save_texture_rejects_non_png():
    with pytest.raises(ServiceError) as exc_info:
        texture_storage.save_texture("skin", b"not a png")
    assert exc_info.value.error_code == "BadRequest"


def test_save_texture_rejects_oversized_file():
    oversized = PNG_HEADER + b"0" * (1024 * 1024)
    with pytest.raises(ServiceError):
        texture_storage.save_texture("skin", oversized)


def test_save_texture_deduplicates_identical_content():
    first_hash = texture_storage.save_texture("cape", FAKE_CAPE)
    second_hash = texture_storage.save_texture("cape", FAKE_CAPE)
    assert first_hash == second_hash
    files = list(texture_storage._storage_dir("cape").glob("*.png"))
    assert len(files) == 1


def test_texture_url_builds_absolute_link():
    url = texture_storage.texture_url("skin", "abc123")
    assert url == "http://test.local/textures/skin/abc123.png"


def test_save_texture_rejects_wrong_size():
    with pytest.raises(ServiceError):
        texture_storage.save_texture("skin", _png(100, 100))
    with pytest.raises(ServiceError):
        texture_storage.save_texture("cape", _png(64, 64))


def test_save_texture_accepts_known_sizes():
    texture_storage.save_texture("skin", _png(64, 32))
    texture_storage.save_texture("skin", _png(128, 128))
    texture_storage.save_texture("cape", _png(64, 32))
    texture_storage.save_texture("cape", _png(22, 17))
