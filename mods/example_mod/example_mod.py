"""example_mod：M5 示例 Mod（全链路验证）。

演示内容：
- mod.json 声明 ``depends: ["pvzpy"]``（依赖内置 Mod）；
- 入口类 :class:`ExampleMod` 在 ``on_pre_init`` 订阅 game_pre_init /
  game_start / game_frame / game_stop 生命周期事件；
- ``on_init`` 通过 Registry 注册自定义植物 :class:`ExamplePlant` 与
  自定义关卡 9-9（M4 注册表对接在 mod 侧的落地）；
- ``assets/`` 同时包含 modID 命名空间资源（example_mod/images/...）与
  mods/example_mod/assets/PVZpy/images/mod.png 覆盖原版资源（M5 覆盖演示）。
"""

from __future__ import annotations

import logging

from src.Entities.Plant import Plant
from src.levels_manager import Level, LevelWave
from src.mod import events
from src.mod.keys import entity_plant_key, level_key

log = logging.getLogger(__name__)

# 模块级记录：供冒烟 / 测试断言事件回调与注册行为
EVENTS_SEEN = []
REGISTERED_KEYS = []


class ExamplePlant(Plant):
    """示例 Mod 注册的自定义植物（占位植物，仅验证注册表生效）。"""

    COST = 25

    def __init__(self, row=1, col=0):
        super().__init__(row, col)
        self.can_attack = False


class ExampleMod:
    """example_mod 入口类：事件订阅 + 注册表注册 + 资源覆盖演示。"""

    def __init__(self) -> None:
        self.manager = None
        self._tokens = []
        self._frame_seen = False

    # ---- 生命周期回调 ----

    def on_pre_init(self, manager) -> None:
        self.manager = manager
        bus = manager.event_bus
        self._tokens.append(bus.subscribe(events.GAME_PRE_INIT, self._on_pre_init))
        self._tokens.append(bus.subscribe(events.GAME_START, self._on_game_start))
        self._tokens.append(bus.subscribe(events.GAME_FRAME, self._on_frame))
        self._tokens.append(bus.subscribe(events.GAME_STOP, self._on_stop))

    def on_init(self, manager) -> None:
        reg = manager.registry
        plant_ok = reg.register(entity_plant_key("ExamplePlant"), ExamplePlant)
        level_ok = reg.register(
            level_key("9-9"),
            Level(
                part=9,
                level=9,
                title="Example Mod 关卡",
                rows=[1] * 5,
                default_plants=["PeaShooter", "ExamplePlant"],
                default_sun=150,
                zombie_types=["Zombie"],
                waves=[LevelWave(delay=60, count=2, zombie_type="Zombie")],
                path="registry:level.9-9",
            ),
        )
        REGISTERED_KEYS.extend(["entity.plant.ExamplePlant", "level.9-9"])
        log.info(
            "example_mod on_init: plant_ok=%s level_ok=%s",
            plant_ok,
            level_ok,
        )

    def on_shutdown(self, manager) -> None:
        for token in self._tokens:
            manager.event_bus.unsubscribe(token)
        self._tokens.clear()

    # ---- 事件处理器 ----

    def _on_pre_init(self, payload) -> None:
        EVENTS_SEEN.append("game_pre_init")

    def _on_game_start(self, payload) -> None:
        ctx = getattr(payload, "context", None)
        EVENTS_SEEN.append(("game_start", ctx is not None))

    def _on_frame(self, payload) -> None:
        if not self._frame_seen:
            self._frame_seen = True
            EVENTS_SEEN.append("game_frame")

    def _on_stop(self, payload) -> None:
        EVENTS_SEEN.append("game_stop")
