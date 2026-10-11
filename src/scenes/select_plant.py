# 选植物：从列表中挑最多 MAX_PLANTS 株，开始后传入冒险场景

import logging

import pygame

from src import GLOBAL_REFERENCE, const, scene_manager
from src.Entities.loader import get_plant_classes
from src.levels_manager import Level, resolve_plant_classes


class SelectPlantScene(scene_manager.Scene):
    NAME = const.SCENE_SELECT_PLANT

    def __init__(self) -> None:
        super().__init__()
        self.all_plants: list = []  # 可选植物类
        self.picked: list = []  # 已选植物类（有序）
        self.item_rects: list[pygame.Rect] = []
        self.start_rect: pygame.Rect | None = None
        self.status_text = ""
        self.level_obj: Level | None = None
        self._auto_start = False

    def on_enter(self) -> None:
        super().on_enter()
        self.level_obj = self._current_level()
        self._auto_start = False
        self.picked = []

        if self.level_obj is not None and not self.level_obj.allow_select_plant:
            # 本关固定植物：直接带上 DefaultPlants
            self.all_plants = resolve_plant_classes(self.level_obj.default_plants) or self._unlocked_plants()
            self.picked = list(self.all_plants)
            self.status_text = f"{self.level_obj.title} 使用固定植物，即将开始"
            self._auto_start = True
            logging.info(
                "SelectPlantScene 固定植物关: %s plants=%s",
                self.level_obj.id,
                [c.__name__ for c in self.picked],
            )
            return

        self.all_plants = self._visible_plants()
        title = self.level_obj.title if self.level_obj else ""
        self.status_text = f"{title}  选择最多 {const.MAX_PLANTS} 株植物，点开始进入冒险"
        logging.info("SelectPlantScene 进入: 可选 %d 种 level=%s", len(self.all_plants), self.level_obj)

    def update(self, dt: float) -> None:
        if self._auto_start:
            self._auto_start = False
            self._start_game()

    def _current_level(self) -> Level | None:
        lm = GLOBAL_REFERENCE.LevelsManager
        completed = GLOBAL_REFERENCE.SavesManager.get("unlocked_levels") or []
        return lm.current_level(completed)

    def _unlocked_plants(self) -> list:
        # 过滤存档 unlocked_plants；未配置或滤空时回退全量
        all_plants = get_plant_classes()
        unlocked = GLOBAL_REFERENCE.SavesManager.get("unlocked_plants")
        if not unlocked:
            return all_plants
        visible = [c for c in all_plants if c.__name__ in unlocked]
        return visible or all_plants

    def _visible_plants(self) -> list:
        # 关卡 DefaultPlants 非空时限制可选范围；再与解锁列表求交
        base = self._unlocked_plants()
        if self.level_obj is None or not self.level_obj.default_plants:
            return base
        allowed = set(self.level_obj.default_plants)
        filtered = [c for c in base if c.__name__ in allowed]
        return filtered or base

    def _toggle(self, cls):
        if cls in self.picked:
            self.picked.remove(cls)
            self.status_text = f"取消 {cls.__name__}  ({len(self.picked)}/{const.MAX_PLANTS})"
            logging.debug("取消选择: %s", cls.__name__)
            return
        if len(self.picked) >= const.MAX_PLANTS:
            self.status_text = f"最多选择 {const.MAX_PLANTS} 株"
            logging.debug("选择已满: %s", cls.__name__)
            return
        self.picked.append(cls)
        self.status_text = f"选择 {cls.__name__}  ({len(self.picked)}/{const.MAX_PLANTS})"
        logging.debug("选择植物: %s", cls.__name__)

    def _start_game(self) -> None:
        if not self.picked:
            self.status_text = "请至少选择 1 株植物"
            logging.warning("未选植物，无法开始")
            return
        level = self.level_obj
        sun = level.default_sun if level is not None else const.START_SUN
        adv = GLOBAL_REFERENCE.SceneManager.scenes.get(const.SCENE_ADVENTURE)
        if adv is not None and hasattr(adv, "setup"):
            adv.setup(
                plant_classes=list(self.picked),
                sun_points=sun,
                level=level.id if level is not None else "",
                level_obj=level,
            )
        logging.info(
            "开始冒险: plants=%s sun=%d level=%s",
            [c.__name__ for c in self.picked],
            sun,
            level.id if level else "-",
        )
        GLOBAL_REFERENCE.SceneManager.switch_to(const.SCENE_ADVENTURE)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                logging.info("SelectPlantScene 返回菜单")
                GLOBAL_REFERENCE.SceneManager.switch_to(const.SCENE_MAIN_MENU)
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button != 1:
            return
        if event.type != pygame.MOUSEBUTTONUP:
            return

        pos = event.pos
        if self.start_rect is not None and self.start_rect.collidepoint(pos):
            self._start_game()
            return
        for i, rect in enumerate(self.item_rects):
            if rect.collidepoint(pos) and i < len(self.all_plants):
                self._toggle(self.all_plants[i])
                return

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(const.UI_BG)
        title, _ = self.font.render("Select Plants", (255, 255, 255), size=26)
        screen.blit(title, title.get_rect(midtop=(const.SCREEN_WIDTH // 2, 16)))
        hint, _ = self.font.render(
            f"已选 {len(self.picked)}/{const.MAX_PLANTS}  ·  ESC 返回",
            const.UI_TEXT_DIM,
            size=16,
        )
        screen.blit(hint, hint.get_rect(midtop=(const.SCREEN_WIDTH // 2, 52)))

        # 植物网格列表
        cols = 5
        card_w, card_h = 140, 64
        gap = 12
        grid_w = cols * card_w + (cols - 1) * gap
        x0 = (const.SCREEN_WIDTH - grid_w) // 2
        y0 = 90
        self.item_rects = []
        for i, cls in enumerate(self.all_plants):
            r, c = divmod(i, cols)
            rect = pygame.Rect(x0 + c * (card_w + gap), y0 + r * (card_h + gap), card_w, card_h)
            self.item_rects.append(rect)
            selected = cls in self.picked
            fill = (46, 90, 48) if selected else const.UI_PANEL
            pygame.draw.rect(screen, fill, rect, border_radius=8)
            pygame.draw.rect(
                screen,
                const.UI_ACCENT if selected else const.UI_BORDER,
                rect,
                width=2,
                border_radius=8,
            )
            name = cls.__name__
            cost = getattr(cls, "COST", "-")
            surf, _ = self.font.render(name, const.UI_TEXT, size=14)
            screen.blit(surf, surf.get_rect(midtop=(rect.centerx, rect.y + 10)))
            cost_s, _ = self.font.render(f"COST {cost}", const.UI_TEXT_DIM, size=12)
            screen.blit(cost_s, cost_s.get_rect(midbottom=(rect.centerx, rect.bottom - 10)))

        # 开始按钮
        self.start_rect = pygame.Rect(0, 0, 220, 48)
        self.start_rect.midbottom = (const.SCREEN_WIDTH // 2, const.SCREEN_HEIGHT - 28)
        ok = len(self.picked) > 0
        pygame.draw.rect(screen, const.UI_ACCENT if ok else const.UI_PANEL, self.start_rect, border_radius=8)
        pygame.draw.rect(screen, const.UI_BORDER, self.start_rect, width=2, border_radius=8)
        label = "Start Adventure" if ok else "Select plants..."
        ts, _ = self.font.render(label, const.UI_TEXT, size=18)
        screen.blit(ts, ts.get_rect(center=self.start_rect.center))

        if self.status_text:
            st, _ = self.font.render(self.status_text, const.UI_TEXT, size=14)
            screen.blit(st, st.get_rect(midbottom=(const.SCREEN_WIDTH // 2, const.SCREEN_HEIGHT - 86)))
