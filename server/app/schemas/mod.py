from pydantic import BaseModel, ConfigDict, Field

from app.models.mod import ModType


class ModOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    file_name: str
    url: str
    file_hash: str
    size: int
    mod_type: ModType
    loader: str
    mc_version: str


class ModUpdate(BaseModel):
    """Частичное обновление: меняются только переданные поля. Сам jar не меняется."""

    name: str | None = Field(None, max_length=128)
    description: str | None = Field(None, max_length=512)
    mod_type: ModType | None = None
    loader: str | None = Field(None, min_length=1, max_length=32)
    mc_version: str | None = Field(None, min_length=1, max_length=32)
