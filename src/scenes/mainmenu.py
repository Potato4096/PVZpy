# 主菜单：文字按钮列表

import logging

import pygame

from src import GLOBAL_REFERENCE, const, scene_manager


def _play_click():
    try:
        GLOBAL_REFERENCE.AssetsManager.get_sound(const.SFX_BUTTON_CLICK).play()
    except Exception as e:
        logging.debug("button click sound failed: %s", e)


class MainMenu(scene_manager.Scene):
    NAME = const.SCENE_MAIN_MENU

    def __init__(self) -> None:
        super().__init__()
        self.items = [
            ("Adventure", self._on_start),
            ("Coming Soon", self._on_unimplemented),
            ("Quit", self._on_quit),
        ]
        self.item_rects: list[pygame.Rect] = []
        self.hover_index = -1
        self._layout()
        self.status_text = ""

    def _layout(self) -> None:
        w, h = 320, 56
        x = (const.SCREEN_WIDTH - w) // 2
        y0 = 220
        self.item_rects = [
            pygame.Rect(x, y0 + i * 72, w, h) for i in range(len(self.items))
        ]

    def on_enter(self) -> None:
        super().on_enter()
        self.status_text = ""
        self.hover_index = -1

    def _on_start(self) -> None:
        _play_click()
        # 冒险：先去选植物
        GLOBAL_REFERENCE.SceneManager.switch_to(const.SCENE_SELECT_PLANT)

    def _on_unimplemented(self) -> None:
        _play_click()
        self.status_text = "Not implemented yet"

    def _on_quit(self) -> None:
        _play_click()
        GLOBAL_REFERENCE.Game.running = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.hover_index = -1
            for i, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos):
                    self.hover_index = i
                    break
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for i, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos):
                    self.items[i][1]()
                    return

    def update(self, dt: float) -> None:
        pass

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(const.UI_BG)
        title, _ = self.font.render("PVZpy", (255, 255, 255), size=52)
        screen.blit(title, title.get_rect(midtop=(const.SCREEN_WIDTH // 2, 80)))
        sub, _ = self.font.render("Plants vs. Zombies Python Edition", const.UI_TEXT_DIM, size=18)
        screen.blit(sub, sub.get_rect(midtop=(const.SCREEN_WIDTH // 2, 150)))

        mouse = pygame.mouse.get_pos()
        for i, ((label, _), rect) in enumerate(zip(self.items, self.item_rects)):
            hot = rect.collidepoint(mouse)
            fill = const.UI_HOVER if hot else const.UI_PANEL
            pygame.draw.rect(screen, fill, rect, border_radius=10)
            pygame.draw.rect(screen, const.UI_BORDER, rect, width=2, border_radius=10)
            text, _ = self.font.render(label, const.UI_TEXT, size=26)
            screen.blit(text, text.get_rect(center=rect.center))

        if self.status_text:
            msg, _ = self.font.render(self.status_text, (255, 220, 120), size=20)
            screen.blit(msg, msg.get_rect(midbottom=(const.SCREEN_WIDTH // 2, const.SCREEN_HEIGHT - 28)))
