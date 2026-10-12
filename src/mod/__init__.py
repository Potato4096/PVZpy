"""PVZpy Mod 系统。

M1 基础设施：提供 Mod 元数据模型（mod_info）、目录扫描与加载器
（loader）、事件总线（event_bus）、泛型注册表（registry）以及统一
管理器（mod_manager）。
"""

from __future__ import annotations

from .event_bus import EventBus
from .mod_info import ModInfo, ModState
from .mod_manager import ModManager
from .registry import Registry

__all__ = [
    "EventBus",
    "ModInfo",
    "ModManager",
    "ModState",
    "Registry",
]
