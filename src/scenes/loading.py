# 启动 Loading：文字 + 简易进度条

import pygame

from src import const, scene_manager
from src.context import GameContext


class LoadingScene(scene_manager.Scene):
    NAME = const.SCENE_LOADING

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.elapsed = 0.0
        self.duration = 1.2
        self.bar = pygame.Rect(200, 340, 400, 28)

    def on_enter(self) -> None:
        super().on_enter()
        self.elapsed = 0.0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_SPACE,
            pygame.K_RETURN,
            pygame.K_ESCAPE,
        ):
            self.elapsed = self.duration
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.elapsed = self.duration

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.context.scene_manager.switch_to(const.SCENE_MAIN_MENU)

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(const.UI_BG)
        progress = min(1.0, self.elapsed / self.duration)

        title, _ = self.font.render("PVZpy", (255, 255, 255), size=48)
        screen.blit(title, title.get_rect(midtop=(const.SCREEN_WIDTH // 2, 120)))

        label, _ = self.font.render("Loading...", const.UI_TEXT, size=28)
        screen.blit(label, label.get_rect(midtop=(const.SCREEN_WIDTH // 2, 220)))

        pygame.draw.rect(screen, const.UI_BORDER, self.bar, border_radius=6)
        inner = self.bar.inflate(-8, -8)
        pygame.draw.rect(screen, const.UI_PANEL, inner, border_radius=4)
        fill_w = int(inner.w * progress)
        if fill_w > 0:
            pygame.draw.rect(screen, const.UI_ACCENT, (inner.x, inner.y, fill_w, inner.h), border_radius=4)

        pct, _ = self.font.render(f"{int(progress * 100)}%", const.UI_TEXT, size=22)
        screen.blit(pct, pct.get_rect(midtop=(const.SCREEN_WIDTH // 2, self.bar.bottom + 16)))
