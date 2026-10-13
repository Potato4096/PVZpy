"""PVZpy_Debugger：F3 切换全屏分块调试界面（类似 Minecraft 调试界面）。

功能：
- F3 按下沿切换调试显示开关（防连发：仅 False->True 边沿触发，长按不重复切换）；
- 开启时在 game_pre_flip（本体 draw 完成后、display.flip 前发布）回调中向全屏绘制
  调试信息层，分四区块：左上=版本+时钟、右上=mod 列表、左下=事件日志、
  右下=FPS 数值+曲线；
- 使用系统字体（微软雅黑/宋体等，match_font/SysFont 选可用中文字体），字体缓存避免
  每帧创建；
- 自维护 FPS 统计（EMA）与最近 N 帧 FPS 历史折线；
- 记录最近若干条生命周期事件；
- 列出已加载 mod（id / 名称 / 版本），游戏版本取内置 pvzpy Mod 元数据
  （const.py 无版本常量，本体现有版本常量为 BUILTIN_PVZPY_INFO.version）。

渲染时机与防闪烁说明：Game.run 每帧顺序为 event_loop -> update -> draw -> GAME_FRAME，
其中 draw() 内部为 screen.fill -> scene.draw -> GAME_PRE_FLIP -> display.flip。
早期版本在 GAME_FRAME（flip 之后）绘制并自行调用 display.flip()：本体内 flip 已发生，
mod 再次 flip 显示的内容会被下一帧 draw 的 fill+重绘+flip 整体覆盖，形成“闪现→被覆盖”
的乱闪。现改为订阅 GAME_PRE_FLIP：绘制发生在本体 flip 之前，由本体统一 flip 一次
提交画面，mod 内不再调用 flip，彻底消除双 flip 竞争。

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

# 配色（无背景覆盖层，彩色文字分区块）
TEXT_MAIN = (255, 255, 255)
TEXT_DIM = (215, 225, 235)
TEXT_ACCENT = (255, 255, 255)
TEXT_MOD = (170, 255, 200)      # mod 列表：浅绿
TEXT_EVENT = (255, 235, 160)    # 事件日志：浅黄
TEXT_FPS = (170, 230, 255)      # FPS：浅青
BLOCK_BORDER = (120, 140, 160)
FPS_CURVE_COLOR = (120, 220, 120)

# 布局与字号（紧凑：标题 22pt / 区块标题 20pt / 正文 17pt，行距 22）
LAYOUT_MARGIN = 16            # 屏幕四周留白
BLOCK_GAP = 16                # 区块间距
BLOCK_PAD = 12                # 区块内边距
LINE_HEIGHT = 22              # 正文字行高（紧凑）
FONT_TITLE = 22               # 大标题（调试器标题 / FPS 数值）
FONT_HEAD = 20                # 区块标题
FONT_BODY = 17                # 正文
FPS_CURVE_H = 70              # 曲线高
FPS_HISTORY_LEN = 120         # FPS 曲线最近 N 帧
EVENT_LOG_LEN = 16            # 最近事件条数
EVENT_SHOW_LEN = 10           # 事件区块最多显示条数
FPS_EMA_ALPHA = 0.15          # 瞬时 fps 的 EMA 平滑系数

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
        self._fonts = {}             # 系统字体缓存 {(size, bold): Font}
        self._overlay = None         # 全屏覆盖层 Surface 缓存（尺寸不变不重建）
        self._overlay_size = None
        self._static_cache = None    # 静态文本渲染缓存（版本/mod 列表等不变内容）
        self._font_is_system = False # 已使用系统字体（match_font/SysFont）

    # ---- 生命周期回调 ----

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
        self._elapsed = 0.0
        self._log_event(events.GAME_START)

    def _on_frame(self, payload) -> None:
        dt = getattr(payload, "dt", 0.0) or 0.0

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

    def _system_font(self, size: int, bold: bool = False):
        """获取缓存的系统字体（微软雅黑/宋体等，按 (size, bold) 缓存避免每帧创建）。"""
        key = (size, bold)
        if key not in self._fonts:
            name = pygame.font.match_font("microsoftyahei,microsoftyaheiui,simsun,arial")
            if name is not None:
                font = pygame.font.Font(name, size)
                font.set_bold(bold)
            else:
                font = pygame.font.SysFont("microsoftyahei,simsun", size, bold=bold)
            self._fonts[key] = font
            self._font_is_system = True
        return self._fonts[key]

    @property
    def font_is_system(self) -> bool:
        """是否已使用系统字体（match_font/SysFont）。"""
        return self._font_is_system

    def _layout_blocks(self, w: int, h: int) -> dict:
        """全屏分块布局（参考 Minecraft 调试界面 + PVZpy 分辨率适配）。

        返回 {left_top, right_top, left_bottom, right_bottom} 四个区块 rect，
        区块之间留 BLOCK_GAP 间距。
        """
        m = LAYOUT_MARGIN
        gap = BLOCK_GAP
        half_w = (w - 2 * m - gap) // 2
        half_h = (h - 2 * m - gap) // 2
        return {
            "left_top": pygame.Rect(m, m, half_w, half_h),
            "right_top": pygame.Rect(m + half_w + gap, m, half_w, half_h),
            "left_bottom": pygame.Rect(m, m + half_h + gap, half_w, half_h),
            "right_bottom": pygame.Rect(m + half_w + gap, m + half_h + gap, half_w, half_h),
        }

    def _ensure_overlay(self, w: int, h: int) -> pygame.Surface:
        """缓存全屏覆盖层 Surface（仅尺寸变化时重建，避免每帧创建）。"""
        if self._overlay is None or self._overlay_size != (w, h):
            self._overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            self._overlay_size = (w, h)
        return self._overlay

    def _draw_block_bg(self, overlay, rect) -> None:
        """绘制分区块边框（无半透明背景填充，仅细边框区分区块）。"""
        pygame.draw.rect(overlay, BLOCK_BORDER, rect, 1)

    def _static_text(self, key: str, text: str, font, color) -> pygame.Surface:
        """缓存不变文本的渲染结果（版本 / mod 行等，减少每帧重复 render）。"""
        if self._static_cache is None:
            self._static_cache = {}
        surf = self._static_cache.get(key)
        if surf is None:
            surf = font.render(text, True, color)
            self._static_cache[key] = surf
        return surf

    def _render_debug(self, game) -> None:
        """在 flip 前向全屏绘制调试层（分四区块，无背景层，不调用 display.flip）。

        布局与样式：字号 22/20/17pt 全 bold，行距紧凑；左栏（左上/左下）文字
        左对齐，右栏（右上/右下）文字右对齐；无半透明背景层（游戏本体 draw
        已 fill 黑色底）；按区块彩色区分：标题白、mod 列表浅绿、事件浅黄、FPS 浅青。
        """
        try:
            surface = getattr(game, "screen", None) or pygame.display.get_surface()
            if surface is None:
                return
            w, h = surface.get_size()
            if w <= 0 or h <= 0:
                return

            overlay = self._ensure_overlay(w, h)
            overlay.fill((0, 0, 0, 0))

            blocks = self._layout_blocks(w, h)
            for rect in blocks.values():
                self._draw_block_bg(overlay, rect)

            title_font = self._system_font(FONT_TITLE, bold=True)
            head_font = self._system_font(FONT_HEAD, bold=True)
            body_font = self._system_font(FONT_BODY, bold=True)

            version = self._game_version()
            clock_s = f"{int(self._elapsed // 60)}:{int(self._elapsed % 60):02d}"
            status = "ON" if self.enabled else "OFF"
            mod_lines = self._mod_lines()
            ev_lines = list(self._event_log)

            # 左上：标题 + 版本 + 时钟（左对齐）
            lt = blocks["left_top"]
            x, y = lt.x + BLOCK_PAD, lt.y + BLOCK_PAD
            overlay.blit(title_font.render(f"PVZpy Debugger ({status})", True, TEXT_ACCENT), (x, y))
            y += FONT_TITLE + 6
            overlay.blit(self._static_text(f"ver:{version}", f"版本: {version}", body_font, TEXT_DIM), (x, y))
            y += LINE_HEIGHT
            overlay.blit(body_font.render(f"时钟: {clock_s}", True, TEXT_MAIN), (x, y))
            y += LINE_HEIGHT
            overlay.blit(body_font.render(f"FPS: {self._fps_ema:.1f} (瞬时 {self._fps_last:.1f})", True, TEXT_MAIN), (x, y))

            # 右上：mod 列表（右对齐，浅绿）
            rt = blocks["right_top"]
            x, y = rt.right - BLOCK_PAD, rt.y + BLOCK_PAD
            head_surf = head_font.render(f"Mod ({len(mod_lines)})", True, TEXT_MOD)
            overlay.blit(head_surf, (x - head_surf.get_width(), y))
            y += FONT_HEAD + 6
            for line in mod_lines:
                if y + LINE_HEIGHT > rt.bottom - BLOCK_PAD:
                    break
                surf = self._static_text(f"mod:{line}", line, body_font, TEXT_MOD)
                overlay.blit(surf, (x - surf.get_width(), y))
                y += LINE_HEIGHT

            # 左下：事件日志（左对齐，浅黄）
            lb = blocks["left_bottom"]
            x, y = lb.x + BLOCK_PAD, lb.y + BLOCK_PAD
            overlay.blit(head_font.render("事件日志", True, TEXT_EVENT), (x, y))
            y += FONT_HEAD + 6
            if ev_lines:
                for line in ev_lines[-EVENT_SHOW_LEN:]:
                    if y + LINE_HEIGHT > lb.bottom - BLOCK_PAD:
                        break
                    overlay.blit(body_font.render(line, True, TEXT_EVENT), (x, y))
                    y += LINE_HEIGHT
            else:
                overlay.blit(body_font.render("(无)", True, TEXT_EVENT), (x, y))

            # 右下：FPS 数值 + 曲线（右对齐，浅青）
            rb = blocks["right_bottom"]
            x, y = rb.right - BLOCK_PAD, rb.y + BLOCK_PAD
            fps_surf = title_font.render(f"{self._fps_ema:.1f} FPS", True, TEXT_FPS)
            overlay.blit(fps_surf, (x - fps_surf.get_width(), y))
            y += FONT_TITLE + 6
            info_surf = body_font.render(f"瞬时: {self._fps_last:.1f}  EMA 平滑", True, TEXT_FPS)
            overlay.blit(info_surf, (x - info_surf.get_width(), y))
            y += LINE_HEIGHT
            curve_w = rb.width - 2 * BLOCK_PAD
            self._draw_fps_curve(overlay, x - curve_w, y, curve_w)

            surface.blit(overlay, (0, 0))
            self._render_called += 1
        except Exception:  # noqa: BLE001 - 调试覆盖层渲染失败不应影响本体/其它 mod
            log.exception("PVZpy_Debugger 渲染失败")

    def _draw_fps_curve(self, overlay, x, y, width) -> None:
        hist = list(self._fps_history)
        n = len(hist)
        if n < 2:
            pygame.draw.rect(overlay, BLOCK_BORDER, (x, y, width, FPS_CURVE_H), 1)
            return
        max_fps = max(60.0, max(hist))
        points = []
        for i, v in enumerate(hist):
            px = x + int(i * (width - 2) / (FPS_HISTORY_LEN - 1))
            py = y + FPS_CURVE_H - 2 - int(v / max_fps * (FPS_CURVE_H - 4))
            points.append((px, py))
        pygame.draw.rect(overlay, BLOCK_BORDER, (x, y, width, FPS_CURVE_H), 1)
        pygame.draw.lines(overlay, FPS_CURVE_COLOR, False, points, 2)
