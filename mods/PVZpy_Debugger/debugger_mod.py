"""PVZpy_Debugger：F3 切换调试面板（类似 Minecraft 调试界面）。

功能：
- F3 按下沿切换调试显示开关（防连发：仅 False->True 边沿触发，长按不重复切换）；
- 开启时在每个 game_frame（渲染后发布）回调中向屏幕顶面绘制调试信息面板；
- 自维护 FPS 统计（EMA）与最近 N 帧 FPS 历史折线；
- 记录最近若干条生命周期事件；
- 列出已加载 mod（id / 名称 / 版本），游戏版本取内置 pvzpy Mod 元数据
  （const.py 无版本常量，本体现有版本常量为 BUILTIN_PVZPY_INFO.version）。

渲染时机说明：Game.run 每帧顺序为 event_loop -> update -> draw -> GAME_FRAME，
即 game_frame 在渲染之后发布，回调中再绘制面板不会被本体覆盖，因此无需修改
本体事件发布时机。

F3 检测：真实环境用 pygame.key.get_pressed() 做按下沿检测（无需依赖事件队列，
因为每帧 event_loop 已消费 KEYDOWN）；无头环境/测试通过公开方法 handle_f3_press()
模拟按下沿，两者都走同一 toggle 逻辑。
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

# 面板与配色（沿用 const.UI_* 相近风格，避免依赖本体模块以保持 mod 独立）
PANEL_BG = (18, 22, 28, 220)
PANEL_BORDER = (70, 85, 105)
PANEL_TEXT = (230, 230, 230)
PANEL_TEXT_DIM = (150, 155, 165)
PANEL_ACCENT = (76, 160, 90)
FPS_CURVE_COLOR = (120, 220, 120)

FPS_CURVE_W = 260          # 曲线宽
FPS_CURVE_H = 56           # 曲线高
FPS_HISTORY_LEN = 120      # FPS 曲线最近 N 帧
EVENT_LOG_LEN = 8          # 最近事件条数
FPS_EMA_ALPHA = 0.15       # 瞬时 fps 的 EMA 平滑系数
PANEL_MARGIN = 10
LINE_HEIGHT = 18
TITLE_FONT_SIZE = 15
BODY_FONT_SIZE = 13


class DebuggerMod:
    """调试器入口类：订阅生命周期事件，F3 切换面板，渲染调试信息。"""

    def __init__(self) -> None:
        self.manager = None
        self._tokens = []
        self.enabled = False
        self._prev_key_down = False
        self._started = False
        self._elapsed = 0.0          # 游戏时钟（运行时长，秒）
        self._fps_ema = 0.0          # EMA 平滑后的 FPS
        self._fps_last = 0.0         # 最近一帧瞬时 FPS
        self._fps_history = deque(maxlen=FPS_HISTORY_LEN)
        self._event_log = deque(maxlen=EVENT_LOG_LEN)
        self._render_called = 0      # 渲染函数调用计数（供冒烟断言）
        self._fonts = {}

    # ---- 生命周期回调 ----

    def on_pre_init(self, manager) -> None:
        self.manager = manager
        bus = manager.event_bus
        # GAME_FRAME 用较高优先级（晚执行）：确保调试面板绘制在其它 mod 处理之后
        self._tokens.append(bus.subscribe(events.GAME_PRE_INIT, self._on_pre_init, priority=100))
        self._tokens.append(bus.subscribe(events.GAME_START, self._on_game_start))
        self._tokens.append(bus.subscribe(events.GAME_FRAME, self._on_frame, priority=100))
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
        self._elapsed = 0.0
        self._log_event(events.GAME_START)

    def _on_frame(self, payload) -> None:
        dt = getattr(payload, "dt", 0.0) or 0.0
        game = getattr(payload, "game", None)

        if self._started:
            self._elapsed += dt

        # 瞬时 FPS + EMA 平滑
        if dt > 0:
            inst = 1.0 / dt
            self._fps_last = inst
            self._fps_ema = inst if self._fps_ema <= 0 else self._fps_ema * (1 - FPS_EMA_ALPHA) + inst * FPS_EMA_ALPHA
        self._fps_history.append(self._fps_ema)

        # F3 按下沿检测（防连发：仅 False->True 边沿切换）
        keys = pygame.key.get_pressed()
        pressed = bool(keys[DEBUG_KEY]) if keys is not None else False
        if pressed and not self._prev_key_down:
            self.toggle()
        self._prev_key_down = pressed

        if self.enabled:
            self._render_debug(game)

    def _on_stop(self, payload) -> None:
        self._log_event(events.GAME_STOP)

    # ---- 对外交互 ----

    def toggle(self) -> None:
        """切换调试显示开关。"""
        self.enabled = not self.enabled
        self._log_event(f"debug_{'on' if self.enabled else 'off'}")

    def handle_f3_press(self) -> None:
        """模拟 F3 按下沿（供无头环境/测试调用，等价于真实按键的沿触发）。"""
        self.toggle()

    # ---- 数据访问（供冒烟断言） ----

    @property
    def fps_ema(self) -> float:
        return self._fps_ema

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

    # ---- 渲染 ----

    def _game_version(self) -> str:
        """游戏版本：优先内置 pvzpy Mod 元数据（const.py 无版本常量）。"""
        try:
            info = self.manager.builtin.info
            return f"{info.friendly_name} v{info.version}"
        except Exception:
            return "PVZpy"

    def _mod_lines(self) -> list:
        lines = []
        for entry in self.manager.loaded:
            info = entry.info
            lines.append(f"{info.id} ({info.friendly_name}) v{info.version}")
        return lines

    def _font(self, size: int):
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    def _render_debug(self, game) -> None:
        """在渲染后向屏幕顶面绘制调试面板（game_frame 在 draw 之后发布）。"""
        try:
            surface = getattr(game, "screen", None) or pygame.display.get_surface()
            if surface is None:
                return
            w = surface.get_width()
            if w <= 0:
                return

            title_font = self._font(TITLE_FONT_SIZE)
            body_font = self._font(BODY_FONT_SIZE)

            version = self._game_version()
            clock_s = f"{int(self._elapsed // 60)}:{int(self._elapsed % 60):02d}"
            status = "ON" if self.enabled else "OFF"
            fps_now = f"{self._fps_ema:.1f}"

            mod_lines = self._mod_lines()
            ev_lines = list(self._event_log)

            panel_x = PANEL_MARGIN
            panel_y = PANEL_MARGIN
            panel_w = min(380, w - 2 * PANEL_MARGIN)
            # 行数 = 标题 + 版本/时钟/FPS + 事件标题 + 事件行 + mod 标题 + mod 行 + 曲线
            row_count = 3 + 1 + len(ev_lines) + 1 + len(mod_lines) + 1
            panel_h = 14 + row_count * LINE_HEIGHT + FPS_CURVE_H

            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill(PANEL_BG)
            pygame.draw.rect(panel, PANEL_BORDER, panel.get_rect(), 1)
            surface.blit(panel, (panel_x, panel_y))

            x = panel_x + 10
            y = panel_y + 8

            def text(s, font=None, color=None):
                nonlocal y
                f = font or body_font
                c = color or PANEL_TEXT
                img = f.render(s, True, c)
                surface.blit(img, (x, y))
                y += LINE_HEIGHT

            text(f"=== PVZpy Debugger ({status}) ===", title_font, PANEL_ACCENT)
            text(f"版本: {version}")
            text(f"时钟: {clock_s}   FPS: {fps_now} (瞬时 {self._fps_last:.1f})")

            # 事件日志
            text("事件:", None, PANEL_TEXT_DIM)
            if ev_lines:
                for line in ev_lines[-6:]:
                    text(line, None, PANEL_TEXT_DIM)
            else:
                text("(无)", None, PANEL_TEXT_DIM)

            # mod 列表
            text(f"Mod ({len(mod_lines)}):", None, PANEL_TEXT_DIM)
            for line in mod_lines:
                text(line, None, PANEL_TEXT_DIM)

            # FPS 曲线
            text("FPS 曲线 (EMA):", None, PANEL_TEXT_DIM)
            self._draw_fps_curve(surface, x, y, panel_w - 20)
            y += FPS_CURVE_H

            self._render_called += 1
            pygame.display.flip()
        except Exception:  # noqa: BLE001 - 调试面板渲染失败不应影响本体/其它 mod
            log.exception("PVZpy_Debugger 渲染失败")

    def _draw_fps_curve(self, surface, x, y, width) -> None:
        hist = list(self._fps_history)
        n = len(hist)
        if n < 2:
            pygame.draw.rect(surface, PANEL_BORDER, (x, y, width, FPS_CURVE_H), 1)
            return
        max_fps = max(60.0, max(hist))
        points = []
        for i, v in enumerate(hist):
            px = x + int(i * (width - 2) / (FPS_HISTORY_LEN - 1))
            py = y + FPS_CURVE_H - 2 - int(v / max_fps * (FPS_CURVE_H - 4))
            points.append((px, py))
        pygame.draw.rect(surface, PANEL_BORDER, (x, y, width, FPS_CURVE_H), 1)
        pygame.draw.lines(surface, FPS_CURVE_COLOR, False, points, 2)
