# 冒险模式：网格种植 + 实体 subclass 列表

import logging
import random

import pygame

from src import const, scene_manager
from src.context import GameContext
from src.Entities.loader import (
    get_bullet_classes,
    get_plant_classes,
    get_zombie_classes,
)
from src.Entities.Sun import Sun
from src.levels_manager import Level, LevelWave, resolve_zombie_class


class AdventureScene(scene_manager.Scene):
    NAME = const.SCENE_ADVENTURE

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.plant_classes: list = []
        self.zombie_classes: list = []
        self.bullet_classes: list = []
        self.selected_index = 0  # 当前选中的植物（对应 plant_classes）
        self.selected_zombie_index = 0  # 当前选中的僵尸（对应 zombie_classes）
        self.seed_rects: list[pygame.Rect] = []
        self.zombie_item_rects: list[pygame.Rect] = []
        self.status_text = ""
        self.sun_points = 0  # 已收集的阳光
        self.elapsed = 0.0
        self.next_sun_at = 5.0  # 第一次天空阳光
        self.level = ""
        self.level_title = ""
        self.map_type = const.MAP_DAY
        self.row_types: list[int] = [const.ROW_LAWN] * const.GRID_ROWS
        self.game_state = "playing"  # playing | win | lose
        self.waves: list = []
        self.wave_index = 0
        self.next_wave_at = 0.0  # 下一波出现时刻（秒，自关卡开始）
        self._setup_plants: list | None = None  # 由选植物场景传入
        self._setup_sun: int | None = None
        self._setup_level: Level | None = None
        self._setup_info: dict = {}

    @property
    def em(self):
        # 实体管理器经 GameContext 注入，不再依赖全局引用
        return self.context.entities

    def setup(
        self,
        plant_classes=None,
        sun_points=None,
        level="",
        level_obj: Level | None = None,
        **info,
    ) -> None:
        # SelectPlantScene / MainMenu 调用：传入本场植物与关卡配置
        self._setup_plants = list(plant_classes) if plant_classes else None
        self._setup_sun = None if sun_points is None else int(sun_points)
        self._setup_level = level_obj
        self.level = level_obj.id if level_obj is not None else level
        self._setup_info = dict(info)
        logging.debug(
            "AdventureScene.setup: plants=%s level=%s obj=%s info=%s",
            [c.__name__ for c in (self._setup_plants or [])],
            self.level,
            None if level_obj is None else level_obj.id,
            self._setup_info,
        )

    def on_enter(self) -> None:
        super().on_enter()
        if self._setup_plants is not None:
            self.plant_classes = self._setup_plants
        else:
            self.plant_classes = get_plant_classes()
        self.zombie_classes = get_zombie_classes()
        self.bullet_classes = get_bullet_classes()
        self.em.clear()
        self.selected_index = 0
        self.selected_zombie_index = 0
        self.elapsed = 0.0
        self.next_sun_at = 5.0
        self.game_state = "playing"
        self.wave_index = 0
        self.next_wave_at = 0.0

        level = self._setup_level
        if level is not None:
            self.level = level.id
            self.level_title = level.title
            self.map_type = level.map_type
            self.row_types = list(level.rows)
            self.waves = list(level.waves)
            self.sun_points = (
                level.default_sun if self._setup_sun is None else self._setup_sun
            )
        else:
            self.level_title = ""
            self.map_type = const.MAP_DAY
            self.row_types = [const.ROW_LAWN] * const.GRID_ROWS
            self.waves = [
                LevelWave(delay=at * const.FPS, count=count, row=row)
                for at, count, row in const.LEVEL_ADVENTURE_1
            ]
            self.sun_points = const.START_SUN if self._setup_sun is None else self._setup_sun

        self.status_text = "左键种植/收阳光；波次自动刷怪；ESC 返回"
        if self.waves:
            first = self.waves[0]
            first_delay = (
                first.delay_seconds if isinstance(first, LevelWave) else float(first[0])
            )
            self.next_wave_at = first_delay
        logging.info(
            "AdventureScene 进入: plants=%s zombies=%s bullets=%s sun=%d level=%s waves=%d next_wave_at=%.2fs",
            [c.__name__ for c in self.plant_classes],
            [c.__name__ for c in self.zombie_classes],
            [c.__name__ for c in self.bullet_classes],
            self.sun_points,
            self.level,
            len(self.waves),
            self.next_wave_at,
        )

    # ── 网格 ──────────────────────────────────────────────

    def cell_rect(self, row, col):
        # row 1-5，col 0-8；换算到像素网格
        x = const.GRID_X + col * const.CELL_W
        y = const.GRID_Y + (row - 1) * const.CELL_H
        return pygame.Rect(x, y, const.CELL_W, const.CELL_H)

    def point_to_cell(self, pos):
        # 返回 (row 1-5, col 0-8)；不在网格内则 None
        x, y = pos
        if x < const.GRID_X or y < const.GRID_Y:
            return None
        col = (x - const.GRID_X) // const.CELL_W
        row0 = (y - const.GRID_Y) // const.CELL_H
        if 0 <= row0 < const.GRID_ROWS and 0 <= col < const.GRID_COLS:
            return int(row0) + 1, int(col)
        return None

    def row_type(self, row: int) -> int:
        # row 为 1-5
        if 1 <= row <= len(self.row_types):
            return int(self.row_types[row - 1])
        return const.ROW_DISABLED

    def can_plant_row(self, row: int) -> bool:
        return self.row_type(row) in (const.ROW_LAWN, const.ROW_POOL)

    def can_spawn_row(self, row: int) -> bool:
        return self.row_type(row) != const.ROW_DISABLED

    def spawnable_rows(self) -> list[int]:
        # 返回 1-5
        return [r for r in range(1, const.GRID_ROWS + 1) if self.can_spawn_row(r)]

    # ── 种植 ──────────────────────────────────────────────

    def selected_plant_class(self):
        if not self.plant_classes:
            return None
        if 0 <= self.selected_index < len(self.plant_classes):
            return self.plant_classes[self.selected_index]
        return None

    def plant_at_cell(self, row, col):
        return self.em.plant_at(row, col)

    def try_plant(self, row: int, col: int) -> bool:
        # row 1-5，col 0-8
        cls = self.selected_plant_class()
        if cls is None:
            self.status_text = "没有可种的植物"
            logging.warning("种植失败: 没有可选植物")
            return False
        if not self.can_plant_row(row):
            self.status_text = f"第 {row} 行不可种植"
            logging.debug("种植失败: 第 %d 行类型 %s 不可种", row, self.row_type(row))
            return False
        if self.plant_at_cell(row, col) is not None:
            self.status_text = "该格已有植物"
            logging.debug("种植失败: (%d,%d) 已有植物", row, col)
            return False
        cost = int(getattr(cls, "COST", 0) or 0)
        if self.sun_points < cost:
            self.status_text = f"阳光不足，需要 {cost}（当前 {self.sun_points}）"
            logging.debug("种植失败: 阳光不足 need=%d have=%d", cost, self.sun_points)
            return False
        plant = cls(row=row, col=col)
        rect = self.cell_rect(row, col)
        plant.x = rect.centerx
        plant.y = rect.centery
        plant.sync_rect()
        self.em.add_plant(plant)
        self.sun_points -= cost
        name = cls.__name__
        eid = plant.entity_id
        self.status_text = f"已种植 {name}#{eid}  ({row},{col})  -{cost} 阳光"
        logging.debug(
            "种植成功: %s#%s at (%d,%d) pos=(%.0f,%.0f) cost=%s sun=%d",
            name, eid, row, col, plant.x, plant.y, cost, self.sun_points,
        )
        return True

    # ── 生成僵尸 ──────────────────────────────────────────

    def selected_zombie_class(self):
        if not self.zombie_classes:
            return None
        if 0 <= self.selected_zombie_index < len(self.zombie_classes):
            return self.zombie_classes[self.selected_zombie_index]
        return self.zombie_classes[0]

    def spawn_zombie(self, row, x=None, zombie_cls=None):
        # row 为 1-5；手动/波次生成。x 缺省在该行最右
        if zombie_cls is None:
            zombie_cls = self.selected_zombie_class()
        if zombie_cls is None:
            self.status_text = "没有僵尸类"
            logging.warning("生成僵尸失败: 列表为空")
            return None
        row_no = int(row)
        if not (1 <= row_no <= const.GRID_ROWS) or not self.can_spawn_row(row_no):
            logging.warning(
                "忽略刷怪: 行 %s 无效或已被 rows 禁用 (type=%s)",
                row,
                self.row_type(row_no) if 1 <= row_no <= const.GRID_ROWS else "out-of-range",
            )
            return None
        if x is None:
            x = const.GRID_X + const.GRID_COLS * const.CELL_W - 16
        y = const.GRID_Y + (row_no - 1) * const.CELL_H + const.CELL_H // 2
        z = zombie_cls(row=row_no, x=float(x), y=float(y))
        self.em.add_zombie(z)
        self.status_text = f"生成僵尸 {z}"
        logging.debug("生成僵尸: %s row=%d x=%.0f", z, row_no, z.x)
        return z

    # ── 事件 ──────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        # 对局结束后：任意点击/按键回菜单
        if self.game_state != "playing":
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONUP):
                logging.info("AdventureScene %s 后返回菜单", self.game_state)
                self.context.scene_manager.switch_to(const.SCENE_MAIN_MENU)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                logging.info("AdventureScene 退出, 当前植物数=%d", len(self.em.plants))
                self.context.scene_manager.switch_to(const.SCENE_MAIN_MENU)
                return
            # Z：调试刷僵尸（轮流换行）
            if event.key == pygame.K_z:
                row = (len(self.em.zombies) % const.GRID_ROWS) + 1
                self.spawn_zombie(row)
                return
            # 数字键 1-9 选植物
            if pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self.plant_classes):
                    self.selected_index = idx
                    cls = self.plant_classes[idx]
                    self.status_text = f"已选择 {cls.__name__}  COST={getattr(cls, 'COST', '-')}"
                    logging.debug("选择植物: %s", cls.__name__)
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            pos = event.pos
            # 优先收集阳光
            if self._try_collect_sun(pos):
                return
            # 点左侧植物列表
            for i, rect in enumerate(self.seed_rects):
                if rect.collidepoint(pos):
                    self.selected_index = i
                    cls = self.plant_classes[i]
                    self.status_text = f"已选择 {cls.__name__}  COST={getattr(cls, 'COST', '-')}"
                    logging.debug("选择植物: %s", cls.__name__)
                    return
            # 点右侧僵尸列表，选要生成的类型
            for i, rect in enumerate(self.zombie_item_rects):
                if rect.collidepoint(pos):
                    self.selected_zombie_index = i
                    cls = self.zombie_classes[i]
                    self.status_text = f"已选择僵尸 {cls.__name__}（右键草坪生成）"
                    logging.debug("选择僵尸类型: %s", cls.__name__)
                    return
            # 点草坪种植
            cell = self.point_to_cell(pos)
            if cell is not None:
                self.try_plant(cell[0], cell[1])
            else:
                logging.debug("点击草坪外: %s", pos)
            return

        # 右键：在点击位置手动生成僵尸
        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            cell = self.point_to_cell(event.pos)
            if cell is None:
                logging.debug("右键不在草坪: %s", event.pos)
                return
            row = cell[0]
            x = event.pos[0]
            self.spawn_zombie(row, x=x)

    def update(self, dt: float) -> None:
        if self.game_state != "playing":
            return
        self.elapsed += dt
        self._try_spawn_waves()
        self.em.update(dt)
        self._try_plant_attack()
        self._try_produce_suns(dt)
        self._cleanup_offscreen()
        self._check_end()

    # ── 波次 / 胜负 ────────────────────────────────────────

    def _try_spawn_waves(self) -> None:
        while self.wave_index < len(self.waves):
            if self.elapsed < self.next_wave_at:
                break
            wave = self.waves[self.wave_index]
            if isinstance(wave, LevelWave):
                count, row, ztype = wave.count, wave.row, wave.zombie_type
            else:
                # 兼容旧 (秒, count, row)：delay 为相对间隔
                count, row = wave[1], wave[2]
                ztype = None
            zombie_cls = resolve_zombie_class(ztype) or self.selected_zombie_class()
            valid = self.spawnable_rows()
            for _ in range(int(count)):
                if row is not None:
                    # 指定行 1-5：禁用则忽略并记录，不改刷其他行
                    r = int(row)
                    if not self.can_spawn_row(r):
                        logging.warning(
                            "忽略刷怪: 指定行 %d 已被 rows 禁用 (type=%s)",
                            r,
                            self.row_type(r),
                        )
                        continue
                    self.spawn_zombie(r, zombie_cls=zombie_cls)
                elif valid:
                    self.spawn_zombie(random.choice(valid), zombie_cls=zombie_cls)
                else:
                    logging.warning("忽略刷怪: 无可用行")
                    break
            logging.info(
                "波次 %d 刷怪 @%.2fs: type=%s count=%s row=%s",
                self.wave_index + 1,
                self.elapsed,
                getattr(zombie_cls, "__name__", ztype),
                count,
                row,
            )
            self.wave_index += 1
            # 下一波：相对当前波次结束时刻 + 下一波的 delay 间隔
            if self.wave_index < len(self.waves):
                nxt = self.waves[self.wave_index]
                gap = (
                    nxt.delay_seconds
                    if isinstance(nxt, LevelWave)
                    else float(nxt[0])
                )
                self.next_wave_at = self.elapsed + gap

    def _cleanup_offscreen(self) -> None:
        margin = 80
        for b in list(self.em.bullets):
            if b.x < -margin or b.x > const.SCREEN_WIDTH + margin:
                b.kill()
        for z in list(self.em.zombies):
            if z.x > const.SCREEN_WIDTH + margin:
                z.kill()
        for s in list(self.em.suns):
            if s.y > const.SCREEN_HEIGHT + margin:
                s.kill()

    def _check_end(self) -> None:
        for z in list(self.em.zombies):
            if z.x < const.LOSE_X:
                self.game_state = "lose"
                self.status_text = "僵尸突破防线！任意键返回"
                logging.info("判负: 僵尸越过 LOSE_X=%s", const.LOSE_X)
                return
        waves_done = self.wave_index >= len(self.waves)
        if waves_done and not any(self.em.zombies):
            self.game_state = "win"
            next_lv = self.context.levels.next_level(self.level)
            if next_lv is not None:
                self.status_text = f"关卡胜利！下一关 {next_lv.title}"
            else:
                self.status_text = "关卡胜利！已通关全部主线"
            logging.info("判胜: 波次打完且无僵尸 level=%s", self.level)
            self._apply_win_save()

    def _apply_win_save(self) -> None:
        sm = self.context.saves
        levels = list(sm.get("unlocked_levels") or [])
        if self.level and self.level not in levels:
            levels.append(self.level)
            sm.set("unlocked_levels", levels)
            logging.info("解锁关卡: %s", self.level)
        plants = list(sm.get("unlocked_plants") or [])
        for cls in get_plant_classes():
            if cls.__name__ not in plants:
                plants.append(cls.__name__)
                sm.set("unlocked_plants", plants)
                logging.info("解锁植物: %s", cls.__name__)
                break

    # ── 阳光 ──────────────────────────────────────────────

    def spawn_sky_sun(self):
        # 天空定时落一颗
        grid_w = const.GRID_COLS * const.CELL_W
        x = const.GRID_X + random.randint(20, grid_w - 20)
        target_y = const.GRID_Y + random.randint(0, const.GRID_ROWS - 1) * const.CELL_H + const.CELL_H // 2
        sun = Sun(x=float(x), y=float(const.GRID_Y - 20), target_y=float(target_y))
        self.em.add_sun(sun)
        logging.debug("天空阳光: %s", sun)
        return sun

    def _try_produce_suns(self, dt):
        # 定时基础阳光
        if self.elapsed >= self.next_sun_at:
            self.spawn_sky_sun()
            self.next_sun_at = self.elapsed + const.SUN_FALL_INTERVAL
        # 向日葵产阳光
        for plant in list(self.em.plants):
            produce = getattr(plant, "try_produce_sun", None)
            if produce is None:
                continue
            if not produce():
                continue
            value = getattr(plant, "SUN_VALUE", Sun.VALUE)
            sun = Sun(
                x=plant.x,
                y=plant.y,
                value=value,
                target_y=plant.y + 24,
            )
            self.em.add_sun(sun)
            logging.debug("向日葵产出: %s from %s", sun, plant)

    def _try_collect_sun(self, pos):
        x, y = pos
        for sun in self.em.suns:
            if sun.alive() and sun.contains(x, y):
                got = sun.collect()
                self.sun_points += got
                self.status_text = f"收集阳光 +{got}，共 {self.sun_points}"
                logging.debug("收集阳光: %s +%d total=%d", sun, got, self.sun_points)
                return True
        return False

    def _try_plant_attack(self):
        # 植物冷却结束且本行有僵尸时，才创建子弹
        for plant in list(self.em.plants):
            if not getattr(plant, "can_attack", False):
                continue
            if not plant.ready_to_attack():
                continue
            make_bullet = getattr(plant, "make_bullet", None)
            if make_bullet is None:
                continue
            # 同行有活僵尸才开火
            if not any(self.em.zombies_in_row(plant.row)):
                continue
            # 传入植物所在位置，子弹从这里飞出
            bullet = make_bullet(x=plant.x + 20, y=plant.y)
            self.em.add_bullet(bullet)
            plant.mark_attacked()
            logging.debug("攻击: %s -> %s", plant, bullet)

    # ── 绘制 ──────────────────────────────────────────────

    def _draw_seeds(self, screen):
        # 顶部横排植物选择
        n = max(1, len(self.plant_classes))
        total_w = n * const.SEED_W + (n - 1) * 8
        x0 = (const.SCREEN_WIDTH - total_w) // 2
        y = const.SEED_Y
        self.seed_rects = []
        for i, cls in enumerate(self.plant_classes):
            rect = pygame.Rect(x0 + i * (const.SEED_W + 8), y, const.SEED_W, const.SEED_H)
            self.seed_rects.append(rect)
            selected = (i == self.selected_index)
            fill = const.UI_HOVER if selected else const.UI_PANEL
            pygame.draw.rect(screen, fill, rect, border_radius=8)
            pygame.draw.rect(screen, const.UI_ACCENT if selected else const.UI_BORDER, rect, width=2, border_radius=8)
            cost = getattr(cls, "COST", "-")
            name = cls.__name__
            label = f"{i + 1}. {name}"
            surf, _ = self.font.render(label, const.UI_TEXT, size=14)
            screen.blit(surf, surf.get_rect(midtop=(rect.centerx, rect.y + 6)))
            cost_s, _ = self.font.render(f"COST {cost}", const.UI_TEXT_DIM, size=12)
            screen.blit(cost_s, cost_s.get_rect(midbottom=(rect.centerx, rect.bottom - 6)))

    def _draw_grid(self, screen):
        for row in range(1, const.GRID_ROWS + 1):
            rtype = self.row_type(row)
            for col in range(const.GRID_COLS):
                rect = self.cell_rect(row, col)
                if rtype == const.ROW_DISABLED:
                    color = (24, 28, 32)
                elif rtype == const.ROW_POOL:
                    color = (36, 70, 110) if (row + col) % 2 == 0 else (30, 60, 98)
                else:
                    color = const.GRID_CELL_A if (row + col) % 2 == 0 else const.GRID_CELL_B
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, const.GRID_LINE, rect, width=1)

                plant = self.plant_at_cell(row, col)
                if plant is not None:
                    pad = 10
                    inner = rect.inflate(-pad * 2, -pad * 2)
                    pygame.draw.rect(screen, const.PLANT_FILL, inner, border_radius=8)
                    name = type(plant).__name__
                    surf, _ = self.font.render(name[:6], (20, 40, 20), size=12)
                    screen.blit(surf, surf.get_rect(center=inner.center))

    def _draw_units(self, screen):
        # 阳光
        for s in self.em.suns:
            r = pygame.Rect(0, 0, s.radius * 2, s.radius * 2)
            r.center = (int(s.x), int(s.y))
            pygame.draw.circle(screen, (240, 210, 60), r.center, s.radius)
            pygame.draw.circle(screen, (200, 160, 30), r.center, s.radius, 2)
        # 僵尸、子弹
        for z in self.em.zombies:
            r = pygame.Rect(0, 0, 28, 36)
            r.center = (int(z.x), int(z.y))
            pygame.draw.rect(screen, const.ZOMBIE_FILL, r, border_radius=4)
            surf, _ = self.font.render(f"Z{z.entity_id}", (255, 220, 220), size=10)
            screen.blit(surf, surf.get_rect(center=r.center))
        for b in self.em.bullets:
            r = pygame.Rect(0, 0, 12, 12)
            r.center = (int(b.x), int(b.y))
            pygame.draw.rect(screen, const.BULLET_FILL, r, border_radius=6)
            surf, _ = self.font.render(f"{b.entity_id}", (40, 40, 20), size=9)
            screen.blit(surf, surf.get_rect(center=r.center))

    def _draw_zombie_picker(self, screen):
        # 底部：僵尸类型（可点选）
        n = max(1, len(self.zombie_classes))
        total_w = n * 120 + (n - 1) * 8
        x0 = (const.SCREEN_WIDTH - total_w) // 2
        y = const.GRID_Y + const.GRID_ROWS * const.CELL_H + 16
        self.zombie_item_rects = []
        title, _ = self.font.render("Zombies (右键草坪生成)", const.UI_ACCENT, size=14)
        screen.blit(title, title.get_rect(midtop=(const.SCREEN_WIDTH // 2, y - 4)))
        y += 24
        for i, cls in enumerate(self.zombie_classes):
            rect = pygame.Rect(x0 + i * 128, y, 120, 28)
            self.zombie_item_rects.append(rect)
            selected = (i == self.selected_zombie_index)
            fill = const.UI_HOVER if selected else const.UI_PANEL
            pygame.draw.rect(screen, fill, rect, border_radius=4)
            pygame.draw.rect(screen, const.UI_BORDER, rect, width=1, border_radius=4)
            line, _ = self.font.render(cls.__name__, const.UI_TEXT, size=12)
            screen.blit(line, line.get_rect(center=rect.center))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(const.UI_BG)

        # 顶部：标题 + 阳光 + 波次
        title_text = self.level_title or "Adventure Mode"
        title, _ = self.font.render(title_text, (255, 255, 255), size=22)
        screen.blit(title, title.get_rect(midtop=(const.SCREEN_WIDTH // 2, 10)))
        sun_label, _ = self.font.render(f"Sun: {self.sun_points}", (240, 210, 60), size=22)
        screen.blit(sun_label, sun_label.get_rect(topright=(const.SCREEN_WIDTH - 20, 12)))
        wave_label, _ = self.font.render(
            f"Wave {min(self.wave_index + 1, len(self.waves))}/{len(self.waves)}",
            const.UI_TEXT_DIM,
            size=14,
        )
        screen.blit(wave_label, wave_label.get_rect(topright=(const.SCREEN_WIDTH - 20, 40)))

        self._draw_seeds(screen)
        self._draw_grid(screen)
        self._draw_units(screen)
        self._draw_zombie_picker(screen)

        if self.status_text:
            surf, _ = self.font.render(self.status_text, const.UI_TEXT, size=16)
            screen.blit(surf, surf.get_rect(midbottom=(const.SCREEN_WIDTH // 2, const.SCREEN_HEIGHT - 12)))

        if self.game_state != "playing":
            self._draw_end_overlay(screen)

    def _draw_end_overlay(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface((const.SCREEN_WIDTH, const.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        if self.game_state == "win":
            text, color = "YOU WIN!", (120, 220, 120)
        else:
            text, color = "THE ZOMBIES ATE YOUR BRAINS", (220, 100, 90)
        surf, _ = self.font.render(text, color, size=36)
        screen.blit(surf, surf.get_rect(center=(const.SCREEN_WIDTH // 2, 260)))
        hint, _ = self.font.render("按任意键返回主菜单", const.UI_TEXT, size=18)
        screen.blit(hint, hint.get_rect(center=(const.SCREEN_WIDTH // 2, 320)))
