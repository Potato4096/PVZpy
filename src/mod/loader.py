"""Mod 加载器。

职责：
- 扫描 mods 目录，定位含 mod.json 的 Mod 目录；
- 解析 mod.json 为 :class:`ModInfo`；
- 将 Mod 目录注入 ``sys.path`` 以便入口模块可导入；
- 按 ``entry_points.main`` 导入入口类并实例化。

id / 命名空间区分大小写原样保留。
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .mod_info import (
    DEFAULT_RESOURCE_DIRS,
    RESOURCE_TYPES,
    ModInfo,
    ModState,
)

MOD_JSON_NAME = "mod.json"


class ModLoadError(RuntimeError):
    """Mod 解析或加载失败。"""


@dataclass
class ModEntry:
    """一次加载得到的 Mod 运行时条目。"""

    info: ModInfo
    mod_dir: Optional[Path] = None          # 外部 Mod 的目录；内置 Mod 为 None
    entry_path: Optional[Path] = None       # 入口模块文件路径（解析用）
    instance: Any = None                    # 入口类实例
    state: ModState = ModState.DISCOVERED
    error: Optional[str] = None
    resource_dirs: Dict[str, Path] = field(default_factory=dict)
    # 各资源类型 -> 实际目录（绝对 Path）。
    # 外部 Mod 相对 mod_dir 解析；内置 Mod（Vanilla.json）相对项目根解析。

    @property
    def id(self) -> str:
        return self.info.id


def find_mod_dirs(mods_dir: Path) -> List[Path]:
    """扫描 mods 目录，返回所有含 mod.json 的 Mod 目录（按目录名排序）。"""
    if not mods_dir.is_dir():
        return []
    dirs = [
        p for p in sorted(mods_dir.iterdir())
        if p.is_dir() and (p / MOD_JSON_NAME).is_file()
    ]
    return dirs


def parse_mod_json(mod_json_path: Path) -> ModInfo:
    """解析 mod.json 为 ModInfo；id 缺失或非字符串时抛 ModLoadError。"""
    try:
        raw = json.loads(mod_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModLoadError(f"无法解析 mod.json: {mod_json_path} ({exc})") from exc

    if not isinstance(raw, dict):
        raise ModLoadError(f"mod.json 顶层必须是对象: {mod_json_path}")

    mod_id = raw.get("id", "")
    if not isinstance(mod_id, str) or not mod_id:
        raise ModLoadError(f"mod.json 缺少非空字符串 id: {mod_json_path}")

    entry_raw = raw.get("entry_points") or {}
    if not isinstance(entry_raw, dict):
        raise ModLoadError(f"entry_points 必须是对象: {mod_json_path}")
    main_entry = entry_raw.get("main")

    def _str_list(value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ModLoadError(f"字段必须是字符串列表: {mod_json_path}")
        return [str(v) for v in value]

    return ModInfo(
        schema_version=int(raw.get("schema_version", 1)),
        id=mod_id,
        friendly_name=str(raw.get("friendly_name", mod_id)),
        version=str(raw.get("version", "1.0.0")),
        version_code=int(raw.get("version_code", 1)),
        authors=_str_list(raw.get("authors")),
        description=str(raw.get("description", "")),
        website=str(raw.get("website", "")),
        entry_points=_entry_points(main_entry),
        depends=_str_list(raw.get("depends")),
        resources=_resources(raw.get("resources"), mod_json_path),
    )


def _resources(value: Any, mod_json_path: Path) -> Dict[str, str]:
    """解析 resources 字段为 {资源类型: 相对路径}。

    - 缺省 / None -> {}（未声明，走默认约定）；
    - 必须是对象；键仅限 assets/levels/entities；值为非空字符串相对路径。
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ModLoadError(f"resources 必须是对象: {mod_json_path}")
    resources: Dict[str, str] = {}
    for key, rel in value.items():
        if key not in RESOURCE_TYPES:
            raise ModLoadError(f"resources 含未知资源类型 {key!r}（可选: {RESOURCE_TYPES}）: {mod_json_path}")
        if not isinstance(rel, str) or not rel:
            raise ModLoadError(f"resources.{key} 必须是非空字符串相对路径: {mod_json_path}")
        resources[key] = rel
    return resources


def _entry_points(main_entry: Any) -> Any:
    from .mod_info import EntryPoints

    if main_entry is None:
        return EntryPoints()
    if not isinstance(main_entry, str) or not main_entry:
        raise ModLoadError("entry_points.main 必须是形如 'module.ClassName' 的字符串")
    return EntryPoints(main=main_entry)


def inject_sys_path(mod_dir: Path) -> None:
    """将 Mod 目录注入 sys.path（幂等，已存在则不重复）。"""
    resolved = str(mod_dir.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def load_entry_point(info: ModInfo, mod_dir: Path) -> Any:
    """按 entry_points.main 导入入口模块并实例化入口类。

    ``main`` 形如 ``my_mod.MainMod``（模块路径.类名）。类名取最后一段，
    前面的部分作为模块导入路径（相对 Mod 目录解析）。
    """
    main = info.entry_points.main
    if not main:
        raise ModLoadError(f"Mod {info.id} 未配置 entry_points.main")
    parts = main.split(".")
    if len(parts) < 2:
        raise ModLoadError(
            f"Mod {info.id} 的 entry_points.main 必须是 'module.ClassName': {main}"
        )
    module_name, class_name = ".".join(parts[:-1]), parts[-1]

    inject_sys_path(mod_dir)
    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except Exception as exc:  # noqa: BLE001 - 加载失败统一包装
        raise ModLoadError(
            f"Mod {info.id} 入口导入失败: {main} ({exc!r})"
        ) from exc
    try:
        return cls()
    except Exception as exc:  # noqa: BLE001
        raise ModLoadError(
            f"Mod {info.id} 入口实例化失败: {class_name} ({exc!r})"
        ) from exc


def compute_resource_dirs(info: ModInfo, base_dir: Path) -> Dict[str, Path]:
    """按 ModInfo.resources 计算各资源类型实际目录（绝对 Path）。

    - 已声明的类型：base_dir / 声明的相对路径；
    - 未声明的类型：base_dir / 默认约定路径（DEFAULT_RESOURCE_DIRS）。
    外部 Mod 的 base_dir 为其 mod 目录；内置 Mod 的 base_dir 为项目根。
    """
    dirs: Dict[str, Path] = {}
    for kind in RESOURCE_TYPES:
        rel = info.resources.get(kind) or DEFAULT_RESOURCE_DIRS[kind]
        dirs[kind] = (base_dir / rel).resolve()
    return dirs


def load_mod_from_dir(mod_dir: Path) -> ModEntry:
    """从目录加载一个外部 Mod（解析元数据 + 导入实例化）。"""
    info = parse_mod_json(mod_dir / MOD_JSON_NAME)
    instance = load_entry_point(info, mod_dir)
    return ModEntry(
        info=info,
        mod_dir=mod_dir,
        entry_path=mod_dir / MOD_JSON_NAME,
        instance=instance,
        state=ModState.LOADED,
        resource_dirs=compute_resource_dirs(info, mod_dir),
    )


def make_builtin_entry(info: ModInfo, entry_cls: type, base_dir: Optional[Path] = None) -> ModEntry:
    """构造内置 Mod 条目（元数据内置，代码不移动，无需 sys.path 注入）。

    传入 base_dir 时按项目根计算 resource_dirs（Vanilla.json 相对项目根）。
    """
    try:
        instance = entry_cls()
    except Exception as exc:  # noqa: BLE001
        raise ModLoadError(f"内置 Mod {info.id} 实例化失败: {exc!r}") from exc
    entry = ModEntry(info=info, instance=instance, state=ModState.LOADED)
    if base_dir is not None:
        entry.resource_dirs = compute_resource_dirs(info, base_dir)
    return entry
