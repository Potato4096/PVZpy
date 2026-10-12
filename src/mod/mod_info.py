"""Mod 元数据模型。

- ``ModInfo``：从 mod.json 解析出的不可变元数据（dataclass(frozen=True)）。
- ``ModState``：Mod 生命周期状态枚举。

规范要点（与开发文档第 3 节一致）：
- id / 命名空间区分大小写，原样保留，不做 lower() 归一化；
- schema_version 用于后续兼容性校验，M1 只记录不强制升级；
- authors / depends 为字符串列表；
- entry_points.main 为入口类全限定名（module:ClassName 或
  module.attr.ClassName），由 loader 负责导入实例化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ModState(Enum):
    """Mod 生命周期状态。"""

    DISCOVERED = "discovered"      # 已扫描到元数据，尚未实例化
    LOADED = "loaded"              # 入口类已导入并实例化
    PRE_INIT = "pre_init"          # on_pre_init 已调用
    ACTIVE = "active"              # on_init 已调用，正常运行
    SHUTDOWN = "shutdown"          # on_shutdown 已调用，已卸载
    FAILED = "failed"              # 加载或初始化失败


@dataclass(frozen=True)
class ModInfo:
    """Mod 清单元数据（对应 mod.json 顶层字段）。

    字段与 mod.json 一一对应：
    schema_version / id / friendly_name / version / version_code /
    authors / description / website / entry_points / depends
    """

    schema_version: int = 1
    id: str = ""
    friendly_name: str = ""
    version: str = "1.0.0"
    version_code: int = 1
    authors: List[str] = field(default_factory=list)
    description: str = ""
    website: str = ""
    entry_points: "EntryPoints" = field(default_factory=lambda: EntryPoints())
    depends: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class EntryPoints:
    """入口点定义。

    main 为入口类全限定名，形如 ``my_mod.MainMod``（模块.类名）。
    """

    main: Optional[str] = None
