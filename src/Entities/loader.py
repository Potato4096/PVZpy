# 实体加载器：导入三个实体包触发子类注册，缓存按基类查询结果

import importlib
import pkgutil
from functools import lru_cache

from src.Entities.Bullet import Bullet
from src.Entities.Plant import Plant
from src.Entities.Zombie import Zombie

_ENTITY_PACKAGES = (
    "src.Entities.Plants",
    "src.Entities.Zombies",
    "src.Entities.Bullets",
)


def _all_subclasses(cls):
    # 递归收集所有子类（不含 cls 自身）
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_all_subclasses(sub))
    return result


def _load_all_entity_modules() -> None:
    # 导入三个包下所有模块，让子类完成注册
    for name in _ENTITY_PACKAGES:
        pkg = importlib.import_module(name)
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.ispkg:
                continue
            importlib.import_module(f"{name}.{info.name}")


@lru_cache(maxsize=None)
def _entity_classes() -> dict[type, tuple]:
    # 首次查询时导入全部实体模块，之后缓存子类清单
    _load_all_entity_modules()
    return {
        Plant: tuple(sorted(_all_subclasses(Plant), key=lambda c: c.__name__)),
        Zombie: tuple(sorted(_all_subclasses(Zombie), key=lambda c: c.__name__)),
        Bullet: tuple(sorted(_all_subclasses(Bullet), key=lambda c: c.__name__)),
    }


def get_plant_classes() -> list:
    return list(_entity_classes()[Plant])


def get_zombie_classes() -> list:
    return list(_entity_classes()[Zombie])


def get_bullet_classes() -> list:
    return list(_entity_classes()[Bullet])
