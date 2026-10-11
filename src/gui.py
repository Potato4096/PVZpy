from collections.abc import Callable

import pygame


class ButtonState:
    NORMAL = 0
    HOVER = 1
    PRESSED = 2
    DISABLED = 3


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        surfaces: pygame.Surface | list[pygame.Surface] | None = None,
        on_hover: Callable | None = None,
        on_click: Callable | None = None,
        on_press: Callable | None = None,
        on_release: Callable | None = None,
        enabled: bool = True,
    ) -> None:
        self.rect = rect
        if surfaces is None:
            surfaces = [pygame.Surface((1, 1), pygame.SRCALPHA)]
        if isinstance(surfaces, list):
            self.surfaces = surfaces
        else:
            self.surfaces = [surfaces]
        self.surface: pygame.Surface = self.surfaces[0]

        self.on_hover = on_hover
        self.on_click = on_click
        self.on_press = on_press
        self.on_release = on_release

        self.enabled = enabled
        self.state = ButtonState.NORMAL if enabled else ButtonState.DISABLED

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.enabled:
            return

        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(event.pos):
                if self.state != ButtonState.HOVER:
                    self.state = ButtonState.HOVER
                    if self.on_hover:
                        self.on_hover()
            else:
                if self.state == ButtonState.HOVER:
                    self.state = ButtonState.NORMAL

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.state = ButtonState.PRESSED
                if self.on_press:
                    self.on_press()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.state == ButtonState.PRESSED:
                if self.rect.collidepoint(event.pos):
                    if self.on_click:
                        self.on_click()
                self.state = ButtonState.NORMAL
                if self.on_release:
                    self.on_release()

    def update(self) -> None:
        if not self.enabled:
            idx = ButtonState.DISABLED if len(self.surfaces) > ButtonState.DISABLED else 0
        else:
            idx = min(self.state, len(self.surfaces) - 1)
        self.surface = self.surfaces[idx]

    def draw(self, screen: pygame.Surface, **kwargs) -> None:
        screen.blit(self.surface, self.rect.topleft, **kwargs)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.state = ButtonState.DISABLED if not enabled else ButtonState.NORMAL


class Dialog:
    def __init__(self, rect: pygame.Rect, surface: pygame.Surface) -> None:
        self.rect = rect
        self.surface = surface

    def draw(self, screen: pygame.Surface, **kwargs) -> None:
        screen.blit(self.surface, self.rect.topleft, **kwargs)
