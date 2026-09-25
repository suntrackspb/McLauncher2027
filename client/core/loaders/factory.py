from core.loaders.base import LoaderStrategy
from core.loaders.mod_loader_strategy import ModLoaderStrategy
from core.loaders.vanilla import VanillaLoader

_MOD_LOADER_IDS = {"forge", "neoforge", "fabric", "quilt"}


def get_loader(loader_id: str) -> LoaderStrategy:
    loader_id = loader_id.lower()
    if loader_id == "vanilla":
        return VanillaLoader()
    if loader_id in _MOD_LOADER_IDS:
        return ModLoaderStrategy(loader_id)
    raise ValueError(f"Неизвестный тип лоадера: {loader_id!r}")
