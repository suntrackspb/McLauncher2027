from pydantic import BaseModel, ConfigDict

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
