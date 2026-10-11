# 场景包。游戏启动时通过 register_builtin_scenes 注册内置场景。


def register_builtin_scenes(scene_manager):
    # 在资源 load_all 完成后调用：Loading → MainMenu
    from src import const
    from src.scenes.adventure import AdventureScene
    from src.scenes.loading import LoadingScene
    from src.scenes.mainmenu import MainMenu
    from src.scenes.select_plant import SelectPlantScene

    scene_manager.add_scene(LoadingScene())
    scene_manager.add_scene(MainMenu())
    scene_manager.add_scene(SelectPlantScene())
    scene_manager.add_scene(AdventureScene())
    scene_manager.switch_to(const.SCENE_LOADING)
