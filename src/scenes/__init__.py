# 场景包。游戏启动时通过 register_builtin_scenes 注册内置场景。

from src.context import GameContext


def register_builtin_scenes(context: GameContext) -> None:
    # 在资源 load_all 完成后调用：Loading → MainMenu
    from src import const
    from src.scenes.adventure import AdventureScene
    from src.scenes.loading import LoadingScene
    from src.scenes.mainmenu import MainMenu
    from src.scenes.select_plant import SelectPlantScene

    scene_manager = context.scene_manager
    scene_manager.add_scene(LoadingScene(context))
    scene_manager.add_scene(MainMenu(context))
    scene_manager.add_scene(SelectPlantScene(context))
    scene_manager.add_scene(AdventureScene(context))
    scene_manager.switch_to(const.SCENE_LOADING)
