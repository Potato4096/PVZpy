"""ModManager 主类。

负责 Mod 生命周期编排：
- ``boot``：先加载内置 pvzpy Mod（元数据内置，代码不移动），再扫描
  mods 目录加载外部 Mod；随后按加载顺序调用 ``on_pre_init`` / ``on_init``。
- ``shutdown``：按加载逆序调用 ``on_shutdown``。

属性：mods / loaded / event_bus / registry / mods_dir。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .event_bus import EventBus
from .loader import ModEntry, ModLoadError, find_mod_dirs, load_mod_from_dir, make_builtin_entry
from .mod_info import ModInfo, ModState
from .registry import Registry

log = logging.getLogger(__name__)

BUILTIN_PVZPY_ID = "pvzpy"

# 内置 pvzpy Mod 元数据（M1：元数据内置，本体代码不移动）。
BUILTIN_PVZPY_INFO = ModInfo(
    schema_version=1,
    id=BUILTIN_PVZPY_ID,
    friendly_name="PVZpy",
    version="1.0.0",
    version_code=1,
    authors=["PVZpy Developers"],
    description="PVZpy 本体，作为内置 Mod 最先加载。",
    website="",
    depends=[],
)


class _BuiltinPVZMod:
    """内置 pvzpy 入口适配类（位于 mod 包内，不移动本体代码）。"""

    def __init__(self) -> None:
        self.manager: Optional[ModManager] = None

    def on_pre_init(self, manager: "ModManager") -> None:
        self.manager = manager

    def on_init(self, manager: "ModManager") -> None:
        pass

    def on_shutdown(self, manager: "ModManager") -> None:
        pass


class ModManager:
    """Mod 系统统一管理器。"""

    def __init__(self, mods_dir: Optional[Path] = None) -> None:
        self.mods_dir = Path(mods_dir) if mods_dir else Path("mods")
        self.event_bus = EventBus()
        self.registry: Registry[object] = Registry()
        # id(区分大小写) -> ModEntry
        self.mods: Dict[str, ModEntry] = {}
        # 加载顺序列表
        self.loaded: List[ModEntry] = []
        self._booted = False

    # ---- 属性 ----

    @property
    def booted(self) -> bool:
        return self._booted

    @property
    def builtin(self) -> Optional[ModEntry]:
        """内置 pvzpy Mod 条目。"""
        return self.mods.get(BUILTIN_PVZPY_ID)

    # ---- 生命周期 ----

    def boot(self) -> None:
        """启动 Mod 系统：加载内置 pvzpy -> 扫描加载外部 Mod -> 执行回调。"""
        if self._booted:
            return

        # 1) 内置 pvzpy 最先加载
        builtin = make_builtin_entry(BUILTIN_PVZPY_INFO, _BuiltinPVZMod)
        self._register_entry(builtin)

        # 2) 扫描 mods 目录，按目录名排序加载外部 Mod
        for mod_dir in find_mod_dirs(self.mods_dir):
            try:
                entry = load_mod_from_dir(mod_dir)
                if entry.info.id in self.mods:
                    log.warning("Mod id 重复，跳过: %s", entry.info.id)
                    continue
                self._register_entry(entry)
            except ModLoadError as exc:
                log.warning("Mod 加载失败 %s: %s", mod_dir, exc)

        # 3) 前置回调（on_pre_init），按加载顺序
        for entry in self.loaded:
            self._call_callback(entry, "on_pre_init", ModState.PRE_INIT)

        # 4) 初始化回调（on_init），按加载顺序
        for entry in self.loaded:
            self._call_callback(entry, "on_init", ModState.ACTIVE)

        self._booted = True

    def shutdown(self) -> None:
        """关闭 Mod 系统：按加载逆序调用 on_shutdown。"""
        for entry in reversed(self.loaded):
            self._call_callback(entry, "on_shutdown", ModState.SHUTDOWN)
        self._booted = False

    def get(self, mod_id: str) -> Optional[ModEntry]:
        """按 id（区分大小写）取 Mod 条目。"""
        return self.mods.get(mod_id)

    # ---- 内部 ----

    def _register_entry(self, entry: ModEntry) -> None:
        self.mods[entry.info.id] = entry
        self.loaded.append(entry)

    def _call_callback(self, entry: ModEntry, method: str, success_state: ModState) -> None:
        callback = getattr(entry.instance, method, None)
        if callback is None:
            # 入口类未实现该回调：视为空操作
            entry.state = success_state
            return
        try:
            callback(self)
            entry.state = success_state
        except Exception as exc:  # noqa: BLE001 - 回调失败只标记状态不中断整体
            entry.state = ModState.FAILED
            entry.error = f"{method} 失败: {exc!r}"
            log.exception("Mod %s 回调 %s 异常", entry.info.id, method)
