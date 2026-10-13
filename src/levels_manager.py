# 关卡管理器：加载 src/Levels/{part}/{level}.json，提供主线关卡查询

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LevelWave:
    # delay：相对上一波的间隔（帧；第一波相对关卡开始）
    # row：指定刷怪行，范围 1-5；None 表示在有效行内随机
    delay: float = 0.0
    count: int = 1
    zombie_type: str | None = None
    row: int | None = None

    @property
    def delay_seconds(self) -> float:
        from src import const

        return float(self.delay) / float(const.FPS)


@dataclass
class Level:
    part: int
    level: int
    title: str = ""
    map_type: str = "Day"
    rows: list[int] = field(default_factory=list)  # 每行类型，见 const.ROW_*
    default_plants: list[str] = field(default_factory=list)
    allow_select_plant: bool = True
    default_sun: int = 50
    zombie_types: list[str] = field(default_factory=list)
    waves: list[LevelWave] = field(default_factory=list)
    path: str = ""

    @property
    def id(self) -> str:
        return f"{self.part}-{self.level}"

    def row_type(self, row: int) -> int:
        # row 为 1-5
        from src import const

        if 1 <= row <= len(self.rows):
            return int(self.rows[row - 1])
        return const.ROW_DISABLED

    def is_row_active(self, row: int) -> bool:
        return self.row_type(row) != 0

    def can_plant_row(self, row: int) -> bool:
        # 草坪/泳池可种；禁用行不可。row 为 1-5
        from src import const

        return self.row_type(row) in (const.ROW_LAWN, const.ROW_POOL)

    def can_spawn_row(self, row: int) -> bool:
        return self.is_row_active(row)

    def active_rows(self) -> list[int]:
        # 返回 1-5 的有效行号
        return [i for i in range(1, len(self.rows) + 1) if self.is_row_active(i)]


def default_rows_for_map(map_type: str) -> list[int]:
    from src import const

    n = const.GRID_ROWS
    if map_type == const.MAP_DAY:
        return [const.ROW_LAWN] * n
    # 未知地图类型：先按白天草坪兜底
    return [const.ROW_LAWN] * n


def _parse_wave(raw: dict) -> LevelWave | None:
    if not isinstance(raw, dict):
        return None
    try:
        row_raw = raw.get("row")
        row = None if row_raw is None else int(row_raw)
        if row is not None and not (1 <= row <= 5):
            logging.warning("波次 row=%s 超出 1-5，忽略指定行: %s", row, raw)
            row = None
        return LevelWave(
            delay=float(raw.get("delay", 0) or 0),  # 单位：帧
            count=int(raw.get("count", 1) or 1),
            zombie_type=raw.get("type") or raw.get("zombie_type") or None,
            row=row,
        )
    except (TypeError, ValueError) as e:
        logging.warning("波次数据无法解析: %s (%s)", raw, e)
        return None


def _parse_level(data: dict, path: Path) -> Level | None:
    try:
        part = int(data.get("part", 0))
        level = int(data.get("level", 0))
    except (TypeError, ValueError):
        logging.warning("关卡缺少合法 part/level: %s", path)
        return None
    if part <= 0 or level <= 0:
        logging.warning("关卡 part/level 必须为正: %s", path)
        return None

    waves: list[LevelWave] = []
    for raw in data.get("Waves") or data.get("waves") or []:
        wave = _parse_wave(raw)
        if wave is not None:
            waves.append(wave)

    title = str(data.get("title") or f"第 {part}-{level} 关")
    map_type = str(data.get("type") or data.get("map_type") or "Day")
    raw_rows = data.get("rows") or data.get("Rows")
    if raw_rows is None:
        rows = default_rows_for_map(map_type)
    else:
        try:
            rows = [int(x) for x in raw_rows]
        except (TypeError, ValueError) as e:
            logging.warning("rows 无法解析 %s: %s，回退默认", path, e)
            rows = default_rows_for_map(map_type)
        # 长度对齐 GRID_ROWS：短则按禁用补齐，长则截断
        from src import const

        n = const.GRID_ROWS
        if len(rows) < n:
            rows = rows + [const.ROW_DISABLED] * (n - len(rows))
        elif len(rows) > n:
            rows = rows[:n]

    default_plants = [str(x) for x in (data.get("DefaultPlants") or data.get("default_plants") or [])]
    zombie_types = [str(x) for x in (data.get("ZombieTypes") or data.get("zombie_types") or [])]
    allow = data.get("AllowSelectPlant", data.get("allow_select_plant", True))
    default_sun = data.get("DefaultSun", data.get("default_sun", 50))

    return Level(
        part=part,
        level=level,
        title=title,
        map_type=map_type,
        rows=rows,
        default_plants=default_plants,
        allow_select_plant=bool(allow),
        default_sun=int(default_sun),
        zombie_types=zombie_types,
        waves=waves,
        path=path.as_posix(),
    )


class LevelsManager:
    # 主线关卡表；levels 按 id 排序

    def __init__(self, registry=None) -> None:
        self.levels: dict[str, Level] = {}
        self.root: Path | None = None
        # M4：可选注册表；mod 关卡经注册表注入，查询时优先注册表、未命中回退内置
        self.registry = registry

    def load_all(self, path) -> None:
        root = Path(path)
        self.root = root
        self.levels.clear()
        self._load_root(root)

    def load_roots(self, roots) -> None:
        """按顺序加载多个关卡根目录（本体优先，后加载的 mod 可覆盖同 id 关卡）。"""
        self.levels.clear()
        roots = [Path(p) for p in roots]
        if roots:
            self.root = roots[0]
        for root in roots:
            self._load_root(root)

    def _load_root(self, root: Path) -> None:
        if not root.is_dir():
            logging.warning("关卡目录不存在: %s", root)
            return
        for file in sorted(root.rglob("*.json")):
            try:
                with open(file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError) as e:
                logging.warning("关卡文件无法读取 %s: %s", file, e)
                continue
            level = _parse_level(data, file)
            if level is None:
                continue
            if level.id in self.levels:
                logging.warning("关卡 id 重复 %s，覆盖 %s", level.id, file)
            self.levels[level.id] = level
            logging.debug("已加载关卡 %s (%s)", level.id, level.title)
        logging.info("Loaded %d levels from %s", len(self.levels), root)

    def _registry_level(self, level_id: str) -> Level | None:
        """M4：从注册表按 level.<id> 取关卡（支持 Level 实例或可解析 dict）。"""
        if self.registry is None:
            return None
        from src.mod.keys import level_key

        try:
            raw = self.registry.get(level_key(level_id))
        except Exception:
            return None
        if isinstance(raw, Level):
            return raw
        if isinstance(raw, dict):
            lv = _parse_level(raw, Path(level_id + ".json"))
            if lv is not None:
                lv.path = f"registry:{level_key(level_id)}"
            return lv
        return None

    def list_levels(self) -> list[Level]:
        # M4：注册表关卡（level.*）与内置关卡合并，同 id 时注册表优先
        items = {lv.id: lv for lv in self.levels.values()}
        if self.registry is not None:
            from src.mod.keys import KEY_LEVEL

            for key in self.registry.enabled_keys:
                if not key.startswith(KEY_LEVEL):
                    continue
                lv = self._registry_level(key[len(KEY_LEVEL):])
                if lv is not None:
                    items[lv.id] = lv
        return sorted(items.values(), key=lambda lv: (lv.part, lv.level))

    def get_level(self, part: int, level: int) -> Level | None:
        return self.get_level_by_id(f"{part}-{level}")

    def get_level_by_id(self, level_id: str) -> Level | None:
        # M4：先查注册表，未命中回退本体内置关卡
        lv = self._registry_level(level_id)
        if lv is not None:
            return lv
        return self.levels.get(level_id)

    def register_builtin_levels(self, registry=None) -> int:
        """M4：将已加载的本体关卡注册到 Registry（level.<id>）。

        registry 为 None（未启用 mod 系统）时跳过；返回新增注册条数。
        """
        if registry is None:
            return 0
        from src.mod.keys import level_key

        count = 0
        for lv in self.list_levels():
            if registry.register(level_key(lv.id), lv):
                count += 1
        return count

    def first_level(self) -> Level | None:
        items = self.list_levels()
        return items[0] if items else None

    def next_level(self, current: Level | str | None) -> Level | None:
        items = self.list_levels()
        if not items:
            return None
        if current is None:
            return items[0]
        cid = current if isinstance(current, str) else current.id
        for i, lv in enumerate(items):
            if lv.id == cid:
                return items[i + 1] if i + 1 < len(items) else None
        return items[0]

    def current_level(self, completed: list[str] | set[str] | None = None) -> Level | None:
        # 主线进度：第一个未通关的关卡；全部通关则回到最后一关可重复刷
        done = set(completed or [])
        items = self.list_levels()
        if not items:
            return None
        for lv in items:
            if lv.id not in done:
                return lv
        return items[-1]


def resolve_plant_classes(names: list[str], registry=None) -> list:
    from src.Entities.loader import all_plant_classes

    by_name = {c.__name__: c for c in all_plant_classes(registry)}
    result = []
    for name in names:
        cls = by_name.get(name)
        if cls is None:
            logging.warning("未知植物类: %s", name)
            continue
        result.append(cls)
    return result


def resolve_zombie_class(name: str | None, registry=None):
    if not name:
        return None
    from src.Entities.loader import all_zombie_classes

    for cls in all_zombie_classes(registry):
        if cls.__name__ == name:
            return cls
    logging.warning("未知僵尸类: %s", name)
    return None
