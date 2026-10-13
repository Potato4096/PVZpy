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


# ---- M4：注册表对接（本体实体接入 Registry，游戏逻辑可查询/回退） ----

def entity_key_for(kind: str, name: str) -> str:
    """构造实体注册键，如 entity_key_for("plant", "PeaShooter") -> "entity.plant.PeaShooter"。"""
    from src.mod import keys

    prefix = {
        "plant": keys.KEY_ENTITY_PLANT,
        "zombie": keys.KEY_ENTITY_ZOMBIE,
        "bullet": keys.KEY_ENTITY_BULLET,
    }.get(kind)
    if prefix is None:
        raise ValueError(f"未知实体类型: {kind}")
    return prefix + name


def register_builtin_entities(registry=None) -> None:
    """M4：将本体全部实体类注册到 Registry（entity.<kind>.<ClassName>）。

    registry 为 None（未启用 mod 系统）时直接返回，保持旧行为不变。
    """
    if registry is None:
        return
    for cls in get_plant_classes():
        registry.register(entity_key_for("plant", cls.__name__), cls)
    for cls in get_zombie_classes():
        registry.register(entity_key_for("zombie", cls.__name__), cls)
    for cls in get_bullet_classes():
        registry.register(entity_key_for("bullet", cls.__name__), cls)


def _registry_classes(registry, prefix: str) -> list:
    """注册表视角的实体类清单（按注册序、去重、排除禁用与非类对象）。"""
    if registry is None:
        return []
    result = []
    seen = set()
    for key in registry.enabled_keys:
        if not key.startswith(prefix):
            continue
        val = registry.get(key)
        if not isinstance(val, type):
            continue
        if id(val) in seen:
            continue
        seen.add(id(val))
        result.append(val)
    return result


def all_plant_classes(registry=None) -> list:
    """M4：注册表视角全部植物类；未启用注册表或无注册项时回退本体内置清单。"""
    from src.mod import keys

    items = _registry_classes(registry, keys.KEY_ENTITY_PLANT)
    return items if items else get_plant_classes()


def all_zombie_classes(registry=None) -> list:
    """M4：注册表视角全部僵尸类；未启用注册表或无注册项时回退本体内置清单。"""
    from src.mod import keys

    items = _registry_classes(registry, keys.KEY_ENTITY_ZOMBIE)
    return items if items else get_zombie_classes()


def all_bullet_classes(registry=None) -> list:
    """M4：注册表视角全部子弹类；未启用注册表或无注册项时回退本体内置清单。"""
    from src.mod import keys

    items = _registry_classes(registry, keys.KEY_ENTITY_BULLET)
    return items if items else get_bullet_classes()
