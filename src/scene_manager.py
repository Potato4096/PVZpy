"""场景系统：Scene 基类与 SceneManager 场景切换器。"""

import logging

import pygame

from src import const
from src.context import GameContext


class Scene:
    """场景基类。

    场景通过构造函数显式接收 GameContext，从中获取资源与管理器依赖，
    不再读取任何模块级全局单例。
    """

    NAME = "BaseScene"

    def __init__(self, context: GameContext) -> None:
        self.context = context
        self.active = False
        self.font = self.context.assets.get_font(const.FONT_PVZ)

    def on_enter(self) -> None:
        """进入场景：激活并准备本场景所需状态。"""
        self.active = True

    def on_exit(self) -> None:
        """退出场景：停止活动状态，交由下一场景接管。"""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        pass


class SceneManager:
    """场景管理器：登记场景并按名称切换（经典状态机式切换）。"""

    def __init__(self) -> None:
        self.scenes: dict[str, Scene] = {}
        self.current_scene: Scene | None = None

    def get_current_scene(self) -> Scene | None:
        return self.current_scene

    def add_scene(self, scene: Scene) -> None:
        self.scenes[scene.NAME] = scene

    def switch_to(self, scene_name: str) -> None:
        # 切换到当前场景本身时保持现状，避免重复触发 on_exit/on_enter
        if self.current_scene is not None and self.current_scene.NAME == scene_name:
            return
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
