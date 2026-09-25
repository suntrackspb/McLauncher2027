from pydantic import BaseModel


class TextureUploadOut(BaseModel):
    ok: bool
    hash: str
