import struct

TEXTURE_KINDS = ("skin", "cape")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_MAX_SIZE_BYTES = 1024 * 1024  # тот же лимит, что у бэкенда (texture_storage.py)


def _png_size(content: bytes) -> tuple[int, int] | None:
    if not content.startswith(_PNG_SIGNATURE) or len(content) < 24 or content[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", content[16:24])


def check_texture(kind: str, content: bytes) -> str | None:
    """Проверка до отправки на бэкенд — те же правила, что в
    server/app/services/texture_storage.py, чтобы игрок увидел понятную
    ошибку сразу, а не после сетевого запроса. None — всё в порядке,
    иначе текст ошибки для UI."""
    size = _png_size(content)
    if size is None:
        return "Файл должен быть PNG"
    if len(content) > _MAX_SIZE_BYTES:
        return "Файл слишком большой (максимум 1 МБ)"

    width, height = size
    if kind == "cape" and (width, height) == (22, 17):
        return None
    if width >= 64 and width % 64 == 0 and width <= 1024:
        if kind == "skin" and height in (width, width // 2):
            return None
        if kind == "cape" and height == width // 2:
            return None
    expected = "64x64 или 64x32" if kind == "skin" else "64x32"
    return f"Картинка {width}x{height}, а нужна {expected}"
