"""M1 mod 系统单元测试。

覆盖：
- mod.json 解析（parse_mod_json 字段与大小写保留、错误处理）
- 事件总线发布订阅与优先级（EventBus）
- 泛型注册表（Registry）
- ModManager.boot 加载内置 pvzpy 与外部 Mod 的生命周期

运行方式（在项目根目录）：
    python -m unittest tools.test_mod_system -v
或直接：
    python tools/test_mod_system.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mod.event_bus import EventBus  # noqa: E402
from src.mod import events  # noqa: E402
from src.mod.loader import (  # noqa: E402
    ModLoadError,
    find_mod_dirs,
    load_entry_point,
    load_mod_from_dir,
    parse_mod_json,
)
from src.mod.mod_info import ModInfo, ModState  # noqa: E402
from src.mod.mod_manager import (  # noqa: E402
    BUILTIN_PVZPY_ID,
    BUILTIN_PVZPY_INFO,
    ModManager,
)
from src.mod.registry import Registry  # noqa: E402
from src.context import GameContext  # noqa: E402


SAMPLE_MOD_JSON = {
    "schema_version": 1,
    "id": "SampleMod",
    "friendly_name": "Sample Mod",
    "version": "2.3.4",
    "version_code": 234,
    "authors": ["Alice", "Bob"],
    "description": "测试用示例 Mod",
    "website": "https://example.com/sample",
    "entry_points": {"main": "sample_mod.SampleMain"},
    "depends": ["pvzpy"],
}

SAMPLE_MAIN_PY = '''\
"""sample_mod 示例入口模块。"""

CALLS = []


class SampleMain:
    def __init__(self):
        self.calls = []

    def on_pre_init(self, manager):
        CALLS.append("pre_init")

    def on_init(self, manager):
        CALLS.append("on_init")

    def on_shutdown(self, manager):
        CALLS.append("on_shutdown")
'''


class TempModsMixin:
    """创建临时 mods 目录与示例 Mod。"""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="pvzpy_mods_")
        self.mods_dir = Path(self._tmp) / "mods"
        self.mods_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def make_sample_mod(self, mod_id="SampleMod", main_cls="SampleMain"):
        mod_dir = self.mods_dir / mod_id
        mod_dir.mkdir()
        data = dict(SAMPLE_MOD_JSON)
        data["id"] = mod_id
        data["entry_points"] = {"main": f"sample_mod.{main_cls}"}
        (mod_dir / "mod.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        (mod_dir / "sample_mod.py").write_text(
            SAMPLE_MAIN_PY.replace("SampleMain", main_cls), encoding="utf-8"
        )
        return mod_dir


class TestParseModJson(unittest.TestCase):
    def test_parse_full_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mod.json"
            path.write_text(json.dumps(SAMPLE_MOD_JSON), encoding="utf-8")
            info = parse_mod_json(path)
        self.assertIsInstance(info, ModInfo)
        self.assertEqual(info.schema_version, 1)
        self.assertEqual(info.id, "SampleMod")
        self.assertEqual(info.friendly_name, "Sample Mod")
        self.assertEqual(info.version, "2.3.4")
        self.assertEqual(info.version_code, 234)
        self.assertEqual(info.authors, ["Alice", "Bob"])
        self.assertEqual(info.description, "测试用示例 Mod")
        self.assertEqual(info.website, "https://example.com/sample")
        self.assertEqual(info.entry_points.main, "sample_mod.SampleMain")
        self.assertEqual(info.depends, ["pvzpy"])

    def test_id_case_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mod.json"
            path.write_text(
                json.dumps({"id": "MyMod", "entry_points": {"main": "a.B"}}),
                encoding="utf-8",
            )
            info = parse_mod_json(path)
        self.assertEqual(info.id, "MyMod")

    def test_missing_id_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mod.json"
            path.write_text(json.dumps({"friendly_name": "no id"}), encoding="utf-8")
            with self.assertRaises(ModLoadError):
                parse_mod_json(path)

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mod.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ModLoadError):
                parse_mod_json(path)


class TestEventBus(unittest.TestCase):
    def test_publish_subscribe(self):
        bus = EventBus()
        got = []
        bus.subscribe("evt", lambda x: got.append(x))
        bus.publish("evt", 42)
        self.assertEqual(got, [42])

    def test_priority_order(self):
        bus = EventBus()
        got = []
        bus.subscribe("evt", lambda: got.append("low"), priority=10)
        bus.subscribe("evt", lambda: got.append("high"), priority=-5)
        bus.subscribe("evt", lambda: got.append("mid"), priority=0)
        bus.publish("evt")
        self.assertEqual(got, ["high", "mid", "low"])

    def test_same_priority_fifo(self):
        bus = EventBus()
        got = []
        bus.subscribe("evt", lambda: got.append(1))
        bus.subscribe("evt", lambda: got.append(2))
        bus.publish("evt")
        self.assertEqual(got, [1, 2])

    def test_unsubscribe_by_token(self):
        bus = EventBus()
        got = []
        token = bus.subscribe("evt", lambda: got.append(1))
        bus.unsubscribe(token)
        bus.publish("evt")
        self.assertEqual(got, [])

    def test_unsubscribe_by_handler(self):
        bus = EventBus()
        got = []

        def h():
            got.append(1)

        bus.subscribe("evt", h)
        self.assertTrue(bus.unsubscribe(h))
        bus.publish("evt")
        self.assertEqual(got, [])

    def test_unsubscribe_all(self):
        bus = EventBus()
        bus.subscribe("a", lambda: None)
        bus.subscribe("a", lambda: None)
        bus.subscribe("b", lambda: None)
        self.assertEqual(bus.unsubscribe_all(), 3)
        self.assertEqual(bus.handler_count, 0)
        bus.publish("a")  # 不应报错

    def test_unsubscribe_all_event(self):
        bus = EventBus()
        bus.subscribe("a", lambda: None)
        bus.subscribe("b", lambda: None)
        self.assertEqual(bus.unsubscribe_all("a"), 1)
        self.assertEqual(bus.handler_count, 1)

    def test_events_isolated(self):
        bus = EventBus()
        got = []
        bus.subscribe("a", lambda: got.append("a"))
        bus.publish("b")
        self.assertEqual(got, [])


class TestRegistry(unittest.TestCase):
    def test_register_get_contains(self):
        reg: Registry[int] = Registry()
        self.assertTrue(reg.register("k1", 100))
        self.assertEqual(reg.get("k1"), 100)
        self.assertTrue(reg.contains("k1"))
        self.assertIsNone(reg.get("missing"))

    def test_duplicate_register_rejected(self):
        reg: Registry[int] = Registry()
        reg.register("k", 1)
        self.assertFalse(reg.register("k", 2))
        self.assertEqual(reg.get("k"), 1)
        self.assertTrue(reg.register("k", 2, replace=True))
        self.assertEqual(reg.get("k"), 2)

    def test_case_sensitive_keys(self):
        reg: Registry[int] = Registry()
        reg.register("Key", 1)
        reg.register("key", 2)
        self.assertEqual(reg.get("Key"), 1)
        self.assertEqual(reg.get("key"), 2)

    def test_disable(self):
        reg: Registry[int] = Registry()
        reg.register("k", 1)
        self.assertTrue(reg.disable("k"))
        self.assertIsNone(reg.get("k"))
        self.assertTrue(reg.contains("k"))
        self.assertFalse(reg.disable("missing"))
        self.assertNotIn("k", reg.enabled_keys)

    def test_all_and_len(self):
        reg: Registry[int] = Registry()
        reg.register("a", 1)
        reg.register("b", 2)
        self.assertEqual(len(reg), 2)
        self.assertEqual(set(reg.all()), {"a", "b"})


class TestLoader(TempModsMixin, unittest.TestCase):
    def test_find_mod_dirs(self):
        self.make_sample_mod()
        dirs = find_mod_dirs(self.mods_dir)
        self.assertEqual(len(dirs), 1)
        self.assertEqual(dirs[0].name, "SampleMod")

    def test_find_mod_dirs_missing(self):
        self.assertEqual(find_mod_dirs(self.mods_dir / "nope"), [])

    def test_load_mod_from_dir(self):
        mod_dir = self.make_sample_mod()
        entry = load_mod_from_dir(mod_dir)
        self.assertEqual(entry.id, "SampleMod")
        self.assertIsNotNone(entry.instance)
        self.assertEqual(entry.state, ModState.LOADED)
        # sys.path 注入应生效：可直接导入入口模块
        import sample_mod  # noqa: F401

    def test_load_entry_point_missing_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            mod_dir = Path(tmp) / "mod"
            mod_dir.mkdir()
            (mod_dir / "mod.json").write_text(
                json.dumps({"id": "X"}), encoding="utf-8"
            )
            info = parse_mod_json(mod_dir / "mod.json")
            with self.assertRaises(ModLoadError):
                load_entry_point(info, mod_dir)


class TestModManagerBoot(TempModsMixin, unittest.TestCase):
    def test_boot_loads_builtin_first(self):
        manager = ModManager(self.mods_dir)
        manager.boot()
        self.assertTrue(manager.booted)
        self.assertEqual(manager.loaded[0].id, BUILTIN_PVZPY_ID)
        self.assertEqual(manager.builtin.id, BUILTIN_PVZPY_ID)
        self.assertEqual(manager.builtin.state, ModState.ACTIVE)
        self.assertEqual(len(manager.mods), 1)

    def test_boot_loads_external_mod_after_builtin(self):
        self.make_sample_mod()
        manager = ModManager(self.mods_dir)
        manager.boot()
        self.assertEqual([e.id for e in manager.loaded], ["pvzpy", "SampleMod"])
        self.assertEqual(manager.mods["SampleMod"].state, ModState.ACTIVE)
        # 内置元数据不依赖 mods 目录文件
        self.assertIs(manager.mods[BUILTIN_PVZPY_ID].info, BUILTIN_PVZPY_INFO)

    def test_external_mod_callbacks_invoked(self):
        self.make_sample_mod()
        import sample_mod  # noqa: F811

        sample_mod.CALLS.clear()
        manager = ModManager(self.mods_dir)
        manager.boot()
        self.assertEqual(sample_mod.CALLS, ["pre_init", "on_init"])
        manager.shutdown()
        self.assertEqual(sample_mod.CALLS, ["pre_init", "on_init", "on_shutdown"])
        self.assertFalse(manager.booted)
        self.assertEqual(manager.mods["SampleMod"].state, ModState.SHUTDOWN)

    def test_duplicate_id_skipped(self):
        # 两个目录同名 id：第二个应被跳过
        self.make_sample_mod(mod_id="Dup")
        mod_dir2 = self.mods_dir / "Dup2"
        mod_dir2.mkdir()
        data = dict(SAMPLE_MOD_JSON)
        data["id"] = "Dup"
        (mod_dir2 / "mod.json").write_text(json.dumps(data), encoding="utf-8")
        (mod_dir2 / "sample_mod.py").write_text(SAMPLE_MAIN_PY, encoding="utf-8")
        manager = ModManager(self.mods_dir)
        manager.boot()
        self.assertEqual(
            [e.id for e in manager.loaded], ["pvzpy", "Dup"]
        )

    def test_boot_without_mods_dir(self):
        empty = Path(tempfile.mkdtemp()) / "no_mods"
        manager = ModManager(empty)
        manager.boot()
        self.assertEqual([e.id for e in manager.loaded], [BUILTIN_PVZPY_ID])


class TestM2EventsAndContext(unittest.TestCase):
    """M2：生命周期事件常量与 GameContext 注入。"""

    def test_lifecycle_event_constants(self):
        self.assertEqual(events.GAME_PRE_INIT, "game_pre_init")
        self.assertEqual(events.GAME_START, "game_start")
        self.assertEqual(events.GAME_FRAME, "game_frame")
        self.assertEqual(events.GAME_STOP, "game_stop")

    def test_event_payloads_exist(self):
        for payload_cls in (
            events.GamePreInitPayload,
            events.GameStartPayload,
            events.GameFramePayload,
            events.GameStopPayload,
        ):
            payload = payload_cls()
            self.assertIsNotNone(payload)

    def test_context_backward_compatible_defaults(self):
        # 不传 mod 字段仍可构造（M2 前代码不受影响）
        ctx = GameContext(
            game=object(),
            assets=object(),
            entities=object(),
            levels=object(),
            saves=object(),
            scene_manager=object(),
        )
        self.assertIsNone(ctx.mod_manager)
        self.assertIsNone(ctx.event_bus)
        self.assertIsNone(ctx.registry)

    def test_context_mod_fields_injected(self):
        manager = ModManager(Path(tempfile.mkdtemp()) / "mods")
        manager.boot()
        ctx = GameContext(
            game=object(),
            assets=object(),
            entities=object(),
            levels=object(),
            saves=object(),
            scene_manager=object(),
            mod_manager=manager,
            event_bus=manager.event_bus,
            registry=manager.registry,
        )
        self.assertIs(ctx.mod_manager, manager)
        self.assertIs(ctx.event_bus, manager.event_bus)
        self.assertIs(ctx.registry, manager.registry)

    def test_bus_publish_exception_can_be_caught(self):
        # mod 事件处理器抛异常时，外层 try/except（游戏 _publish_safe 同款）
        # 可捕获，不拖垮本体逻辑。
        bus = EventBus()

        def boom(_payload):
            raise RuntimeError("mod broken")

        bus.subscribe(events.GAME_FRAME, boom)
        try:
            bus.publish(events.GAME_FRAME, events.GameFramePayload())
        except RuntimeError:
            pass
        else:  # pragma: no cover
            self.fail("事件处理器异常应向外传播以被保护层捕获")


class TestM4RegistryIntegration(unittest.TestCase):
    """M4：本体内置内容接入 Registry（实体 / 关卡）。

    验证点：注册表为 None 或为空时回退本体内置清单；注册表命中时优先
    返回注册项；关卡查询注册表优先、未命中回退内置。
    """

    def test_register_builtin_entities_none_registry_safe(self):
        # registry=None 时应直接返回，不抛异常（未启用 mod 系统保持旧行为）
        from src.Entities.loader import register_builtin_entities

        register_builtin_entities(None)

    def test_all_plant_classes_without_registry_fallback(self):
        from src.Entities.loader import all_plant_classes

        items = all_plant_classes(None)
        self.assertTrue(items)
        names = {c.__name__ for c in items}
        self.assertIn("PeaShooter", names)

    def test_all_plant_classes_empty_registry_fallback(self):
        from src.Entities.loader import all_plant_classes

        reg = Registry()
        items = all_plant_classes(reg)
        self.assertTrue(items)
        names = {c.__name__ for c in items}
        self.assertIn("PeaShooter", names)

    def test_registry_plant_preferred(self):
        from src.Entities.loader import all_plant_classes
        from src.mod.keys import entity_plant_key

        class DummyPlant:
            pass

        reg = Registry()
        reg.register(entity_plant_key("DummyPlant"), DummyPlant)
        items = all_plant_classes(reg)
        # 注册表有植物项时不再回退内置
        self.assertEqual(len(items), 1)
        self.assertIs(items[0], DummyPlant)

    def test_registry_zombie_resolve(self):
        from src.Entities.loader import all_zombie_classes
        from src.mod.keys import entity_zombie_key

        class BossZombie:
            pass

        reg = Registry()
        reg.register(entity_zombie_key("BossZombie"), BossZombie)
        items = all_zombie_classes(reg)
        self.assertEqual(len(items), 1)
        self.assertIs(items[0], BossZombie)

    def test_registry_bullet_preferred(self):
        from src.Entities.loader import all_bullet_classes
        from src.mod.keys import entity_bullet_key

        class MagicBullet:
            pass

        reg = Registry()
        reg.register(entity_bullet_key("MagicBullet"), MagicBullet)
        items = all_bullet_classes(reg)
        self.assertEqual(len(items), 1)
        self.assertIs(items[0], MagicBullet)

    def test_entity_key_prefixes(self):
        from src.mod.keys import (
            entity_bullet_key,
            entity_plant_key,
            entity_zombie_key,
            level_key,
        )

        self.assertEqual(entity_plant_key("A"), "entity.plant.A")
        self.assertEqual(entity_zombie_key("B"), "entity.zombie.B")
        self.assertEqual(entity_bullet_key("C"), "entity.bullet.C")
        self.assertEqual(level_key("1-1"), "level.1-1")

    def test_register_builtin_levels_into_registry(self):
        from src import const
        from src.levels_manager import LevelsManager
        from src.mod.keys import level_key

        lm = LevelsManager()
        lm.load_all(const.LEVELS_DIR)
        reg = Registry()
        count = lm.register_builtin_levels(reg)
        self.assertGreater(count, 0)
        self.assertTrue(reg.contains(level_key("1-1")))

    def test_get_level_by_id_fallback_builtin(self):
        from src import const
        from src.levels_manager import LevelsManager

        lm = LevelsManager()
        lm.load_all(const.LEVELS_DIR)
        self.assertIsNotNone(lm.get_level_by_id("1-1"))
        self.assertIsNone(lm.get_level_by_id("no-such-level"))

    def test_get_level_by_id_registry_priority(self):
        from src import const
        from src.levels_manager import Level, LevelsManager
        from src.mod.keys import level_key

        reg = Registry()
        lm = LevelsManager(registry=reg)
        lm.load_all(const.LEVELS_DIR)
        lm.register_builtin_levels(reg)
        custom = Level(part=7, level=7, title="Registry Level", rows=[1] * 5)
        reg.register(level_key("1-1"), custom, replace=True)
        got = lm.get_level_by_id("1-1")
        self.assertIsNotNone(got)
        self.assertEqual(got.title, "Registry Level")

    def test_list_levels_merges_registry(self):
        from src import const
        from src.levels_manager import Level, LevelsManager
        from src.mod.keys import level_key

        reg = Registry()
        lm = LevelsManager(registry=reg)
        lm.load_all(const.LEVELS_DIR)
        lm.register_builtin_levels(reg)
        custom = Level(part=8, level=8, title="Custom", rows=[1] * 5)
        reg.register(level_key("8-8"), custom)
        ids = {lv.id for lv in lm.list_levels()}
        self.assertIn("8-8", ids)
        self.assertIn("1-1", ids)

    def test_resolve_zombie_class_registry(self):
        from src.levels_manager import resolve_zombie_class
        from src.mod.keys import entity_zombie_key

        class TinyZombie:
            pass

        reg = Registry()
        reg.register(entity_zombie_key("TinyZombie"), TinyZombie)
        self.assertIs(resolve_zombie_class("TinyZombie", reg), TinyZombie)

    def test_resolve_plant_classes_registry(self):
        from src.levels_manager import resolve_plant_classes
        from src.mod.keys import entity_plant_key

        class GoldenSunflower:
            pass

        reg = Registry()
        reg.register(entity_plant_key("GoldenSunflower"), GoldenSunflower)
        items = resolve_plant_classes(["GoldenSunflower"], reg)
        self.assertEqual(len(items), 1)
        self.assertIs(items[0], GoldenSunflower)


if __name__ == "__main__":
    unittest.main(verbosity=2)
