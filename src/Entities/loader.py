# 自动加载实体子类：扫描 Plants / Zombies / Bullets 包

import importlib
import pkgutil

from src.Entities.Bullet import Bullet
from src.Entities.Plant import Plant
from src.Entities.Zombie import Zombie


def _all_subclasses(cls):
    # 递归收集所有子类（不含 cls 自身）
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_all_subclasses(sub))
    return result


def load_all_entity_modules():
    # 导入三个包下所有模块，让子类完成注册
    packages = [
        "src.Entities.Plants",
        "src.Entities.Zombies",
        "src.Entities.Bullets",
    ]
    for name in packages:
        pkg = importlib.import_module(name)
        for info in pkgutil.iter_modules(pkg.__path__):
            if info.ispkg:
                continue
            importlib.import_module(f"{name}.{info.name}")


def get_plant_classes():
    load_all_entity_modules()
    return sorted(_all_subclasses(Plant), key=lambda c: c.__name__)


def get_zombie_classes():
    load_all_entity_modules()
    return sorted(_all_subclasses(Zombie), key=lambda c: c.__name__)


def get_bullet_classes():
    load_all_entity_modules()
    return sorted(_all_subclasses(Bullet), key=lambda c: c.__name__)
