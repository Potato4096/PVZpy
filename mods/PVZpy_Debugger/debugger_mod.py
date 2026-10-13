"""PVZpy_Debugger：按桌面旧版（PVZpy-Debugger-main）重写的调试器模组。

界面与旧版保持一致：
- 左上角单列调试信息（每行黄色 consolas 14pt，逐行半透明黑底 alpha 160，行距 18）：
  游戏版本 / FPS / Tick（帧计数）/ Scene / Mouse / Click（左右键按住状态）/
  Mods / User；
- 右下角 FPS 折线图（120x60 半透明黑底、黄色 FPS 标题、绿色折线、最近 120 帧）；
- F3 切换显示/隐藏，默认显示。

内部实现改为当前 mod 系统接口：
- 生命周期：on_pre_init / on_init / on_shutdown（由 ModManager 驱动，
  废弃旧版 @mod_manager.register + on_load 钩子）；
- 事件总线：订阅 GAME_PRE_INIT / GAME_START / GAME_FRAME /
  GAME_EVENT_LOOP / GAME_PRE_FLIP / GAME_STOP（废弃旧版
  hook("game_init"/"before_event"/"after_draw")）；
- 渲染时机：GAME_PRE_FLIP（本体 draw 完成后、display.flip 前发布），
  绘制在 flip 之前由本体统一 flip 一次，mod 不自行 flip（消除双 flip 闪烁）；
- F3 检测：GAME_FRAME 中用 pygame.key.get_pressed() 做按下沿检测
  （不消费事件队列；无头环境/测试用 handle_f3_press() 模拟同一 toggle 逻辑）；
- GAME_EVENT_LOOP：本体消费事件前用 pygame.event.peek() 非破坏探测事件
  类型并记录日志（不调用 get()，不干扰本体事件分发）；
- 命名空间资源：图标置于 mods/PVZpy_Debugger/assets/images/icon.png，
  由 Game 构造期按 mod id 命名空间注册（AssetsManager），
  废弃旧版 "assets/PVZpy-Debugger/images/icon.png" 裸资源 key。

数据来源映射（旧版 -> 当前接口）：
  game.clock.get_fps()            -> game.clock.get_fps()（同）
  game.tick_count                 -> 本模组每帧自增的帧计数
  scene.name                      -> game.current_scene.NAME（场景类常量）
  game.mouse_pos                  -> pygame.mouse.get_pos()（实时鼠标坐标）
  game.mouse_click                -> pygame.mouse.get_pressed(3)（左右键按住状态）
  mod_manager.active_mods         -> manager.loaded（当前已加载 mod 列表）
  game.username                   -> game.context.saves.current_user
  "PVZpy v0.0.7-dev" 硬编码       -> 内置 pvzpy Mod 元数据（friendly_name + version）
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime

import pygame

from src.mod import events

log = logging.getLogger(__name__)

# 调试键
DEBUG_KEY = pygame.K_F3

# 配色（与旧版一致）
TEXT_YELLOW = (255, 255, 0)
FPS_CURVE_COLOR = (0, 255, 0)
BG_ALPHA = 160
CHART_BG_ALPHA = 160

# 布局（与旧版一致）
TEXT_X_BG = 8          # 每行背景 x
TEXT_X = 12            # 每行文字 x
TEXT_Y_START = 10      # 首行文字 y
TEXT_LINE_STEP = 18    # 行距
FONT_SIZE = 14
FONT_NAME = "consolas"

# FPS 折线图（右下角，与旧版一致）
CHART_W = 120
CHART_H = 60
CHART_MARGIN_X = 130   # 距右边缘
CHART_MARGIN_Y = 80    # 距下边缘
FPS_HISTORY_LEN = 120

# 事件日志 peek 探测类型（pygame.event.peek 仅返回 bool，按类型名显示）
EVENT_PEEK_TYPES = [
    pygame.QUIT,
    pygame.KEYDOWN,
    pygame.KEYUP,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.MOUSEWHEEL,
    pygame.VIDEORESIZE,
    pygame.USEREVENT,
    pygame.TEXTINPUT,
]


class DebuggerMod:
    """调试器入口类：订阅当前 mod 系统事件，F3 切换，渲染旧版调试界面。"""

    def __init__(self) -> None:
        self.manager = None
        self._tokens = []
        # 与旧版一致：默认显示调试信息
        self.enabled = True
        self._prev_key_down = False
        self._started = False
        self._frame_count = 0      # Tick：帧计数（旧版 game.tick_count 的等价替代）
        self._fps_history = deque(maxlen=FPS_HISTORY_LEN)
        self._event_log = deque(maxlen=16)
        self._render_called = 0    # 渲染函数调用计数（供冒烟断言）
        self._font = None

    # ---- 生命周期回调（当前 mod 系统接口） ----

    def on_pre_init(self, manager) -> None:
        self.manager = manager
        bus = manager.event_bus
        # GAME_PRE_FLIP 在 draw 之后、本体 flip 之前发布：调试覆盖层在此绘制，
        # 由本体统一 flip 一次显示（不自行 flip，避免双 flip 乱闪）。
        self._tokens.append(bus.subscribe(events.GAME_PRE_INIT, self._on_pre_init, priority=100))
        self._tokens.append(bus.subscribe(events.GAME_START, self._on_game_start))
        self._tokens.append(bus.subscribe(events.GAME_FRAME, self._on_frame))
        self._tokens.append(bus.subscribe(events.GAME_EVENT_LOOP, self._on_event_loop, priority=100))
        self._tokens.append(bus.subscribe(events.GAME_PRE_FLIP, self._on_pre_flip, priority=100))
        self._tokens.append(bus.subscribe(events.GAME_STOP, self._on_stop, priority=100))

    def on_init(self, manager) -> None:
        self._log_event("mod_init")

    def on_shutdown(self, manager) -> None:
        for token in self._tokens:
            manager.event_bus.unsubscribe(token)
        self._tokens.clear()
        self._log_event("mod_shutdown")

    # ---- 事件处理器 ----

    def _on_pre_init(self, payload) -> None:
        self._log_event(events.GAME_PRE_INIT)

    def _on_game_start(self, payload) -> None:
        self._started = True
        self._frame_count = 0
        self._log_event(events.GAME_START)

    def _on_frame(self, payload) -> None:
        if self._started:
            self._frame_count += 1

        # F3 按下沿检测（防连发：仅 False->True 边沿切换，不消费事件队列）
        keys = pygame.key.get_pressed()
        pressed = bool(keys[DEBUG_KEY]) if keys is not None else False
        if pressed and not self._prev_key_down:
            self.toggle()
        self._prev_key_down = pressed

    def _on_pre_flip(self, payload) -> None:
        """本体 draw 之后、flip 之前：绘制调试覆盖层（不调用 flip）。"""
        game = getattr(payload, "game", None)
        if game is None:
            return
        if not self.enabled:
            return
        self._render_debug(game)

    def _on_event_loop(self, payload) -> None:
        """event_loop 消费 pygame 事件队列之前：用 pygame.event.peek() 非破坏性
        探测待处理事件类型并记录（pygame-ce 的 peek 仅返回 bool，故按类型名显示；
        不调用 get()，不影响本体 event_loop 对事件队列的消费）。"""
        try:
            found = []
            for ev_type in EVENT_PEEK_TYPES:
                try:
                    if pygame.event.peek(ev_type):
                        name = pygame.event.event_name(ev_type).upper()
                        if name and name not in found:
                            found.append(name)
                except Exception:  # noqa: BLE001 - 单类型探测失败不影响整体
                    continue
            for name in found:
                self._log_event(name)
        except Exception:  # noqa: BLE001 - 事件探测失败不应影响本体/其它 mod
            log.debug("PVZpy_Debugger peek 事件探测失败", exc_info=True)

    def _on_stop(self, payload) -> None:
        self._log_event(events.GAME_STOP)

    # ---- 对外交互 ----

    def toggle(self) -> None:
        """切换调试显示开关（与旧版 F3 切换一致）。"""
        self.enabled = not self.enabled
        self._log_event(f"debug_{'on' if self.enabled else 'off'}")

    def handle_f3_press(self) -> None:
        """模拟 F3 按下沿（供无头环境/测试调用，等价于真实按键的沿触发）。"""
        self.toggle()

    # ---- 数据访问（供冒烟断言） ----

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def fps_history_len(self) -> int:
        return len(self._fps_history)

    @property
    def event_log_entries(self):
        return list(self._event_log)

    @property
    def render_called(self) -> int:
        return self._render_called

    def _log_event(self, name: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self._event_log.append(f"[{now}] {name}")

    # ---- 数据收集（与旧版信息行一一对应） ----

    def _game_version(self) -> str:
        """游戏版本：优先内置 pvzpy Mod 元数据（const.py 无版本常量）。"""
        try:
            info = self.manager.builtin.info
            return f"{info.friendly_name} v{info.version}"
        except Exception:
            return "PVZpy"

    def _info_lines(self, game) -> list:
        """构建旧版左上角信息行（供渲染与冒烟断言复用）。"""
        fps = int(game.clock.get_fps())
        scene = game.current_scene
        scene_name = scene.NAME if scene is not None else "None"
        mouse = pygame.mouse.get_pos()
        buttons = pygame.mouse.get_pressed(3)  # (left, middle, right)
        left = int(bool(buttons[0]))
        right = int(bool(buttons[2]))

        lines = [
            self._game_version(),
            f"FPS: {fps}",
            f"Tick: {self._frame_count}",
            "---",
            f"Scene: {scene_name}",
            f"Mouse: ({mouse[0]}, {mouse[1]})",
            f"Click: L={left} R={right}",
            "---",
            f"Mods: {len(self.manager.loaded)}",
            f"User: {game.context.saves.current_user}",
        ]
        return lines

    # ---- 渲染（与旧版界面一致） ----

    def _render_debug(self, game) -> None:
        """在 flip 前绘制旧版调试界面（左上信息块 + 右下 FPS 折线图）。"""
        try:
            if self._font is None:
                self._font = pygame.font.SysFont(FONT_NAME, FONT_SIZE)
            surface = getattr(game, "screen", None) or pygame.display.get_surface()
            if surface is None:
                return
            w, h = surface.get_size()
            if w <= 0 or h <= 0:
                return

            fps = int(game.clock.get_fps())

            # 左上角：逐行黄字 + 半透明黑底
            lines = self._info_lines(game)
            y = TEXT_Y_START
            for line in lines:
                text_surf = self._font.render(line, True, TEXT_YELLOW)
                bg = pygame.Surface((text_surf.get_width() + 8, text_surf.get_height() + 2))
                bg.fill((0, 0, 0))
                bg.set_alpha(BG_ALPHA)
                surface.blit(bg, (TEXT_X_BG, y - 1))
                surface.blit(text_surf, (TEXT_X, y))
                y += TEXT_LINE_STEP

            # 右下角：FPS 折线图
            self._fps_history.append(fps)
            if len(self._fps_history) > FPS_HISTORY_LEN:
                self._fps_history.popleft()

            chart_x = w - CHART_MARGIN_X
            chart_y = h - CHART_MARGIN_Y

            bg_surf = pygame.Surface((CHART_W, CHART_H), pygame.SRCALPHA)
            bg_surf.fill((0, 0, 0, CHART_BG_ALPHA))
            surface.blit(bg_surf, (chart_x, chart_y))

            title = self._font.render(f"FPS: {fps}", True, TEXT_YELLOW)
            surface.blit(title, (chart_x + 2, chart_y - 16))

            if len(self._fps_history) >= 2:
                max_fps = max(self._fps_history)
                points = []
                for i, f in enumerate(self._fps_history):
                    px = chart_x + (i / max(len(self._fps_history) - 1, 1)) * CHART_W
                    py = chart_y + CHART_H - (f / max(max_fps, 1)) * CHART_H
                    points.append((px, py))
                pygame.draw.lines(surface, FPS_CURVE_COLOR, False, points, 1)

            self._render_called += 1
        except Exception:  # noqa: BLE001 - 调试覆盖层渲染失败不应影响本体/其它 mod
            log.exception("PVZpy_Debugger 渲染失败")
