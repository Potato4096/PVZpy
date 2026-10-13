"""M5 冒烟：60 帧游戏主循环 + 示例 mod 全链路验证。

验证项（任一失败则非零退出）：
1. example_mod 由 ModManager 正常加载并 ACTIVE
2. 事件总线回调生效：game_pre_init / game_start / game_frame / game_stop 均被记录
3. 注册表内容生效：ExamplePlant 植物与 9-9 关卡注册且可从注册表视角查询
4. 资源覆盖生效：PVZpy/images/mod.png 命中 mod 覆盖（16x16）；modID 命名空间资源可解析
5. 60 帧主循环完整跑完（GAME_FRAME 发布次数 >= 60）
6. 本体外置：src/Vanilla.json 存在且 id=pvzpy、ModManager 读取其元数据（非硬编码默认）
7. 启动顺序：本体（pvzpy）最先初始化，外部 mod 在其后按目录序
8. 资源分发：本体 assets=assets/PVZpy 被收集；未声明 resources 的 mod 走默认约定；
   声明自定义路径的 mod 按声明目录分发

运行方式（项目根目录，SDL dummy）：
    python tools/smoke_mod_system.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from src import const  # noqa: E402
from src.assets_manager import AssetsManager  # noqa: E402
from src.Entities.loader import all_plant_classes  # noqa: E402
from src.game import Game  # noqa: E402
from src.levels_manager import LevelsManager  # noqa: E402
from src.mod import events  # noqa: E402
from src.mod.keys import entity_plant_key, level_key  # noqa: E402
from src.mod.loader import parse_mod_json  # noqa: E402
from src.mod.mod_manager import VANILLA_JSON_PATH, ModManager  # noqa: E402

FRAMES = 60
FAILURES = []


def check(name: str, cond: bool) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name)
    if not cond:
        FAILURES.append(name)


def main() -> int:
    # 1) 外部创建并 boot ModManager（等价 main 入口）
    manager = ModManager(mods_dir=const.PROJECT_ROOT / "mods")
    manager.boot()

    # 2) 构造 Game（发布 game_pre_init，注册 mod 命名空间、本体资源、内置注册表内容）
    game = Game(mod_manager=manager)
    # 隔离存档写入，避免污染项目真实存档
    game.context.saves.save_dir = Path(tempfile.mkdtemp(prefix="pvzpy_smoke_"))

    # 3) 60 帧计数器：第 60 帧时结束主循环
    frame_count = {"n": 0}

    def _count_frames(payload) -> None:
        frame_count["n"] += 1
        if frame_count["n"] >= FRAMES:
            game.running = False

    bus = manager.event_bus
    token = bus.subscribe(events.GAME_FRAME, _count_frames)

    # 4) 资源覆盖断言（display 活跃时执行；run 结束会 pygame.quit）
    assets: AssetsManager = game.context.assets
    surf = assets.get_surface(f"{const.BUILTIN_NAMESPACE}/images/mod.png")
    card = assets.get_surface("example_mod/images/example_plant_card.png")

    # 5) 跑完整 60 帧主循环（内部发布 game_start / game_frame / game_stop）
    game.run()
    bus.unsubscribe(token)

    # 6) 断言
    import example_mod

    print("== M5 冒烟检查点 ==")
    check("example_mod 加载且 ACTIVE", "example_mod" in manager.mods)
    check(
        "注册表含 ExamplePlant/9-9",
        manager.registry.contains(entity_plant_key("ExamplePlant"))
        and manager.registry.contains(level_key("9-9")),
    )
    names = {c.__name__ for c in all_plant_classes(manager.registry)}
    check("注册表视角含 ExamplePlant", "ExamplePlant" in names)
    lm = LevelsManager(registry=manager.registry)
    lm.load_all(const.LEVELS_DIR)
    lv = lm.get_level_by_id("9-9")
    check("关卡管理器可查询 9-9", lv is not None and lv.title == "Example Mod 关卡")

    seen = example_mod.EVENTS_SEEN
    check("事件回调 game_pre_init", "game_pre_init" in seen)
    check("事件回调 game_start", ("game_start", True) in seen)
    check("事件回调 game_frame", "game_frame" in seen)
    check("事件回调 game_stop", "game_stop" in seen)

    check("资源覆盖生效 PVZpy/images/mod.png=16x16", surf.get_size() == (16, 16))
    check("modID 命名空间资源可解析 24x24", card.get_size() == (24, 24))

    check(f"60 帧主循环完整（实际 {frame_count['n']} 帧）", frame_count["n"] >= FRAMES)

    # 7) M6 检查点：本体外置 Vanilla.json + 启动顺序 + 资源分发
    print("== M6 冒烟检查点（Vanilla.json / 启动顺序 / 资源分发）==")
    check("src/Vanilla.json 存在", VANILLA_JSON_PATH.is_file())
    vanilla_info = parse_mod_json(VANILLA_JSON_PATH)
    check("Vanilla.json id=pvzpy", vanilla_info.id == "pvzpy")
    check(
        "Vanilla.json 声明 assets=assets/PVZpy",
        vanilla_info.resources.get("assets") == "assets/PVZpy",
    )
    builtin_info = manager.builtin.info
    check(
        "ModManager 读取 Vanilla.json 元数据（非硬编码默认）",
        builtin_info.friendly_name == vanilla_info.friendly_name
        and builtin_info.resources.get("assets") == "assets/PVZpy",
    )
    check("启动顺序：本体最先初始化", manager.loaded[0].id == "pvzpy")
    loaded_ids = [e.id for e in manager.loaded]
    check(
        "启动顺序：example_mod 位于本体之后",
        loaded_ids.index("example_mod") > loaded_ids.index("pvzpy"),
    )
    builtin_dirs = manager.builtin.resource_dirs
    check(
        "本体 assets 分发为 assets/PVZpy",
        builtin_dirs["assets"] == const.ASSETS_BUILTIN_DIR.resolve(),
    )
    check(
        "本体 levels 分发为 src/Levels",
        builtin_dirs["levels"] == const.LEVELS_DIR.resolve(),
    )
    ex_entry = manager.mods["example_mod"]
    check(
        "未声明 resources 的 mod 走默认约定 assets/",
        ex_entry.resource_dirs["assets"] == (ex_entry.mod_dir / "assets").resolve(),
    )
    # 声明自定义资源路径的 mod：临时 boot 一个只含该 mod 的 ModManager 验证分发
    tmp_mods_root = Path(tempfile.mkdtemp(prefix="pvzpy_modres_"))
    tmp_mod_dir = tmp_mods_root / "MyResMod"
    tmp_mod_dir.mkdir()
    (tmp_mod_dir / "mod.json").write_text(
        '{"schema_version":1,"id":"MyResMod","friendly_name":"Res Mod",'
        '"version":"1.0.0","entry_points":{"main":"res_mod.ResMain"},'
        '"resources":{"assets":"my_assets","levels":"my_levels","entities":"my_entities"}}',
        encoding="utf-8",
    )
    (tmp_mod_dir / "res_mod.py").write_text(
        "class ResMain:\n"
        "    def on_pre_init(self, manager): pass\n"
        "    def on_init(self, manager): pass\n",
        encoding="utf-8",
    )
    tmp_manager = ModManager(mods_dir=tmp_mods_root)
    tmp_manager.boot()
    tmp_dirs = tmp_manager.resource_dirs("assets")
    check(
        "声明自定义 assets 路径的 mod 按声明目录分发",
        len(tmp_dirs) == 2
        and tmp_dirs[0] == const.ASSETS_BUILTIN_DIR.resolve()
        and tmp_dirs[1] == (tmp_mod_dir / "my_assets").resolve(),
    )
    check(
        "声明自定义 levels/entities 路径同样分发",
        tmp_manager.resource_dirs("levels")[1] == (tmp_mod_dir / "my_levels").resolve()
        and tmp_manager.resource_dirs("entities")[1] == (tmp_mod_dir / "my_entities").resolve(),
    )

    print()
    if FAILURES:
        print(f"冒烟结果: FAIL {len(FAILURES)} 项")
        return 1
    print("冒烟结果: 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
