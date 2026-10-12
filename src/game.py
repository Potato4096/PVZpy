"""游戏主循环：初始化 Pygame 与全部管理器，构造 GameContext 并向下注入。"""

from typing import Optional

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
from src.mod import events
from src.mod.mod_manager import ModManager
from src.scenes import register_builtin_scenes


class Game:
    def __init__(self, mod_manager: Optional[ModManager] = None) -> None:
        pygame.init()
        pygame.mixer.init()
        pygame.freetype.init()
        self.screen = pygame.display.set_mode((const.SCREEN_WIDTH, const.SCREEN_HEIGHT))
        pygame.display.set_caption("Plants vs. Zombies Python Edition")
        self.clock = pygame.time.Clock()
        self.running = True

        # M2：mod 系统接入。外部（main 入口）已创建并 boot 时直接复用；
        # 否则兜底自建（mods_dir 指向项目根 mods/，不存在则创建）。
        if mod_manager is None:
            mod_manager = self._create_default_mod_manager()
        self.mod_manager = mod_manager

        # 构造应用上下文：显式持有各管理器与场景管理器，向下游依赖注入
        self.context = GameContext(
            game=self,
            assets=assets_manager.AssetsManager(),
            entities=entities_manager.EntitiesManager(),
            levels=levels_manager.LevelsManager(),
            saves=saves_manager.SavesManager(),
            scene_manager=scene_manager.SceneManager(),
            mod_manager=self.mod_manager,
            event_bus=self.mod_manager.event_bus,
            registry=self.mod_manager.registry,
        )

        # 发布 game_pre_init：mod 系统已 boot，资源加载前，mod 可预先注册服务
        self._publish_safe(
            events.GAME_PRE_INIT,
            events.GamePreInitPayload(context=self.context),
        )

        self.context.assets.load_all(const.ASSETS_DIR)
        self.context.levels.load_all(const.LEVELS_DIR)
        self.context.saves.load_all(const.SAVES_DIR)

        register_builtin_scenes(self.context)

    @staticmethod
    def _create_default_mod_manager() -> ModManager:
        mods_dir = const.PROJECT_ROOT / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        manager = ModManager(mods_dir=mods_dir)
        manager.boot()
        return manager

    @property
    def current_scene(self) -> scene_manager.Scene | None:
        return self.context.scene_manager.get_current_scene()

    def run(self) -> None:
        self._publish_safe(
            events.GAME_START,
            events.GameStartPayload(context=self.context),
        )
        while self.running:
            dt = self.clock.tick(const.FPS) / 1000.0
            self.event_loop()
            self.update(dt)
            self.draw(self.screen)
            self._publish_safe(
                events.GAME_FRAME,
                events.GameFramePayload(dt=dt, game=self),
            )
        self._publish_safe(
            events.GAME_STOP,
            events.GameStopPayload(context=self.context),
        )
        self.context.saves.save()
        self.mod_manager.shutdown()
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

    # ---- 事件发布（带保护） ----

    def _publish_safe(self, event: str, payload: object) -> None:
        """发布生命周期事件；mod 订阅方异常不得拖垮本体游戏逻辑。"""
        bus = self.context.event_bus
        if bus is None:
            return
        try:
            bus.publish(event, payload)
        except Exception:  # noqa: BLE001 - mod 事件处理器异常仅记录
            import logging

            logging.getLogger(__name__).exception("mod 事件处理异常: %s", event)
