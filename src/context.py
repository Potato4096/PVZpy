"""游戏共享上下文。

聚合 Game 与各 Manager，作为显式依赖注入给场景等下游，替代裸全局可变单例
GLOBAL_REFERENCE。本模块仅做类型引用（TYPE_CHECKING），不导入任何运行时对象，
从而切断 manager / 场景之间的循环导入。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src import (
        assets_manager,
        entities_manager,
        game,
        levels_manager,
        saves_manager,
        scene_manager,
    )
    from src.mod import event_bus, mod_manager, registry


@dataclass
class GameContext:
    """应用上下文：持有 Game 与全部管理器引用。

    依赖方向：Game 负责构造 context 并向下传递；场景等只从 context 取用所需
    管理器，不再依赖任何模块级全局可变状态。
    """

    game: game.Game
    assets: assets_manager.AssetsManager
    entities: entities_manager.EntitiesManager
    levels: levels_manager.LevelsManager
    saves: saves_manager.SavesManager
    scene_manager: scene_manager.SceneManager

    # ---- M2 新增：mod 系统引用（向后兼容，未接入时默认 None） ----
    mod_manager: Optional["mod_manager.ModManager"] = None
    event_bus: Optional["event_bus.EventBus"] = None
    registry: Optional["registry.Registry"] = None
