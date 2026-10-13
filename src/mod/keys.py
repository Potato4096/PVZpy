"""M4：本体可扩展内容在 Registry 中的注册键约定。

键 = 前缀 + 具体名称（区分大小写原样保留）。Mod 可通过同一键注册自定义
内容，或在明确授权下覆盖本体内容（register(replace=True)）。

- 实体类：``entity.plant.<ClassName>`` / ``entity.zombie.<ClassName>`` / ``entity.bullet.<ClassName>``
- 关卡：``level.<part>-<level>``
"""

KEY_ENTITY_PLANT = "entity.plant."
KEY_ENTITY_ZOMBIE = "entity.zombie."
KEY_ENTITY_BULLET = "entity.bullet."
KEY_LEVEL = "level."


def entity_plant_key(name: str) -> str:
    return KEY_ENTITY_PLANT + name


def entity_zombie_key(name: str) -> str:
    return KEY_ENTITY_ZOMBIE + name


def entity_bullet_key(name: str) -> str:
    return KEY_ENTITY_BULLET + name


def level_key(level_id: str) -> str:
    return KEY_LEVEL + level_id
