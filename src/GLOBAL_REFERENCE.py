from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 只在静态类型检查时导入,运行时不会执行,循环导入被切断
    from src import (
        assets_manager,
        entities_manager,
        game,
        levels_manager,
        saves_manager,
        scene_manager,
    )

# 这些注解在运行时不会求值(靠 __future__ annotations),
# 所以即使名称在运行时不存在也没关系
Game: game.Game
AssetsManager: assets_manager.AssetsManager
EntitiesManager: entities_manager.EntitiesManager
LevelsManager: levels_manager.LevelsManager
SceneManager: scene_manager.SceneManager
SavesManager: saves_manager.SavesManager