from pathlib import Path

import pygame
import pygame.freetype

from src import (
    GLOBAL_REFERENCE,
    assets_manager,
    const,
    entities_manager,
    levels_manager,
    saves_manager,
    scene_manager,
)
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

        GLOBAL_REFERENCE.AssetsManager = assets_manager.AssetsManager()
        GLOBAL_REFERENCE.EntitiesManager = entities_manager.EntitiesManager()
        GLOBAL_REFERENCE.LevelsManager = levels_manager.LevelsManager()
        GLOBAL_REFERENCE.SceneManager = scene_manager.SceneManager()
        GLOBAL_REFERENCE.SavesManager = saves_manager.SavesManager()

        GLOBAL_REFERENCE.AssetsManager.load_all(const.ASSETS_DIR)
        GLOBAL_REFERENCE.LevelsManager.load_all(const.LEVELS_DIR)
        GLOBAL_REFERENCE.SavesManager.load_all(const.SAVES_DIR)

        register_builtin_scenes(GLOBAL_REFERENCE.SceneManager)

    @property
    def current_scene(self) -> scene_manager.Scene | None:
        return GLOBAL_REFERENCE.SceneManager.get_current_scene()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(const.FPS) / 1000.0
            self.event_loop()
            self.update(dt)
            self.draw(self.screen)
        GLOBAL_REFERENCE.SavesManager.save()
        pygame.quit()

    def event_loop(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            GLOBAL_REFERENCE.SceneManager.handle_event(event)

    def update(self, dt: float) -> None:
        GLOBAL_REFERENCE.SceneManager.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill((0, 0, 0))
        GLOBAL_REFERENCE.SceneManager.draw(screen)
        pygame.display.flip()
