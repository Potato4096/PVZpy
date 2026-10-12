"""泛型注册表。

以字符串 id 为键的通用对象注册表。id 区分大小写原样保留；重复注册
默认拒绝（可 disable 覆盖），M1 供 Mod 注册自己的服务/对象。
"""

from __future__ import annotations

from typing import Dict, Generic, Iterator, List, Optional, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """泛型注册表：register / get / contains / all / disable。"""

    def __init__(self) -> None:
        self._items: Dict[str, T] = {}
        self._disabled: set = set()

    def register(self, key: str, value: T, *, replace: bool = False) -> bool:
        """注册对象。key 已存在且 replace=False 时返回 False。"""
        if key in self._items and not replace:
            return False
        self._items[key] = value
        self._disabled.discard(key)
        return True

    def get(self, key: str) -> Optional[T]:
        """按 key 取对象；未注册或已禁用返回 None。"""
        if key in self._disabled:
            return None
        return self._items.get(key)

    def contains(self, key: str) -> bool:
        """是否已注册（含禁用项）。"""
        return key in self._items

    def all(self) -> Dict[str, T]:
        """返回全部已注册对象（含禁用项）的拷贝。"""
        return dict(self._items)

    def disable(self, key: str) -> bool:
        """禁用指定注册项（保留注册关系，get 不再返回）；未注册返回 False。"""
        if key not in self._items:
            return False
        self._disabled.add(key)
        return True

    @property
    def enabled_keys(self) -> List[str]:
        """当前可用（未禁用）的 key 列表。"""
        return [k for k in self._items if k not in self._disabled]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)
