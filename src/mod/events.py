"""核心生命周期事件定义。

事件名常量 + 事件 Payload。发布统一走 EventBus.publish(event, payload)，
保持现有事件总线签名不变（publish(event, *args, **kwargs)）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---- 事件名常量 ----

GAME_PRE_INIT = "game_pre_init"
"""游戏预初始化：Mod 系统已 boot，GameContext 已构造，资源加载前。"""

GAME_START = "game_start"
"""游戏主循环开始（第一帧渲染前）。"""

GAME_FRAME = "game_frame"
"""每一帧更新/渲染完成后发布，携带 dt（秒）。"""

GAME_PRE_FLIP = "game_pre_flip"
"""每帧绘制完成后、display.flip 之前发布，供覆盖层（如调试 UI）融入本体渲染管线。"""

GAME_STOP = "game_stop"
"""游戏主循环退出后、存档与 Mod 卸载前发布。"""


# ---- Payload ----

@dataclass(frozen=True)
class GamePreInitPayload:
    """game_pre_init 事件载荷。"""

    context: Any = None


@dataclass(frozen=True)
class GameStartPayload:
    """game_start 事件载荷。"""

    context: Any = None


@dataclass(frozen=True)
class GameFramePayload:
    """game_frame 事件载荷。"""

    dt: float = 0.0
    game: Any = None


@dataclass(frozen=True)
class GamePreFlipPayload:
    """game_pre_flip 事件载荷。"""

    dt: float = 0.0
    game: Any = None


@dataclass(frozen=True)
class GameStopPayload:
    """game_stop 事件载荷。"""

    context: Any = None
