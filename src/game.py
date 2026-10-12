"""游戏主循环：初始化 Pygame 与全部管理器，构造 GameContext 并向下注入。"""

import pygame
import pygame.freetype

from src import (
    assets_manager,
    const,
    entities_manager,
    levels_manager,
    saves_manager,
    scene_manager,
)
from src.context import GameContext
from src.scenes import register_builtin_scenes


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.mixer.init()
        pygame.freetype.init()
        self.screen = pygame.display.set_mode((const.SCREEN_WIDTH, const.SCREEN_HEIGHT))
        pygame.display.set_caption("Plants vs. Zombies Python Edition")
        self.clock = pygame.time.Clock()
        self.running = True

        # 构造应用上下文：显式持有各管理器与场景管理器，向下游依赖注入
        self.context = GameContext(
            game=self,
            assets=assets_manager.AssetsManager(),
            entities=entities_manager.EntitiesManager(),
            levels=levels_manager.LevelsManager(),
            saves=saves_manager.SavesManager(),
            scene_manager=scene_manager.SceneManager(),
        )
        self.context.assets.load_all(const.ASSETS_DIR)
        self.context.levels.load_all(const.LEVELS_DIR)
        self.context.saves.load_all(const.SAVES_DIR)

        register_builtin_scenes(self.context)

    @property
    def current_scene(self) -> scene_manager.Scene | None:
        return self.context.scene_manager.get_current_scene()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(const.FPS) / 1000.0
            self.event_loop()
            self.update(dt)
            self.draw(self.screen)
        self.context.saves.save()
        pygame.quit()

    def event_loop(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            self.context.scene_manager.handle_event(event)

    def update(self, dt: float) -> None:
        self.context.scene_manager.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
        self.context.scene_manager.draw(screen)
        pygame.display.flip()
