import logging

import pygame


class Scene:
    NAME = "BaseScene"

    def __init__(self) -> None:
        self.active = False
        self.font = self._load_default_font()

    def _load_default_font(self):
        # 函数内 import，避免 scene_manager ↔ GLOBAL_REFERENCE 循环导入
        from src import GLOBAL_REFERENCE, const

        return GLOBAL_REFERENCE.AssetsManager.get_font(const.FONT_PVZ)

    def on_enter(self) -> None:
        self.active = True

    def on_exit(self) -> None:
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass


class SceneManager:
    def __init__(self) -> None:
        self.scenes: dict[str, Scene] = {}
        self.current_scene: Scene | None = None

    def get_current_scene(self) -> Scene | None:
        return self.current_scene

    def add_scene(self, scene: Scene) -> None:
        self.scenes[scene.NAME] = scene

    def switch_to(self, scene_name: str) -> None:
        if self.current_scene:
            self.current_scene.on_exit()
        self.current_scene = self.scenes.get(scene_name)
        if self.current_scene:
            self.current_scene.on_enter()
        else:
            logging.warning(
                "SceneManager: scene '%s' not found. Registered: %s",
                scene_name,
                list(self.scenes.keys()),
            )

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.current_scene:
            self.current_scene.handle_event(event)

    def update(self, dt: float) -> None:
        if self.current_scene:
            self.current_scene.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        if self.current_scene:
            self.current_scene.draw(screen)
