"""轻量事件总线。

支持按事件名订阅/发布/退订，同一事件可按优先级排序执行处理器
（数字越小越先执行，默认 0）。M1 供 Mod 之间解耦通信使用。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

Handler = Callable[..., Any]
Token = int


class EventBus:
    """同步事件总线。

    线程模型：M1 为单线程同步调用，publish 按优先级升序同步执行所有
    处理器；若后续需要异步可在此类上扩展。
    """

    def __init__(self) -> None:
        # event -> list[(priority, seq, handler)]
        self._handlers: Dict[str, List[Tuple[int, int, Handler]]] = {}
        self._seq = 0

    def subscribe(
        self, event: str, handler: Handler, priority: int = 0
    ) -> Token:
        """订阅事件，返回可用于退订的 token。

        priority 越小越先执行；同优先级按订阅先后执行。
        """
        self._seq += 1
        self._handlers.setdefault(event, []).append(
            (priority, self._seq, handler)
        )
        self._handlers[event].sort(key=lambda item: (item[0], item[1]))
        return self._seq

    def publish(self, event: str, *args: Any, **kwargs: Any) -> None:
        """发布事件，按优先级顺序同步调用全部处理器。"""
        for _prio, _seq, handler in tuple(self._handlers.get(event, ())):
            handler(*args, **kwargs)

    def unsubscribe(self, token_or_handler: Union[Token, Handler]) -> bool:
        """按 token 或处理器引用退订；成功返回 True，未找到返回 False。"""
        removed = False
        for event, entries in list(self._handlers.items()):
            for entry in list(entries):
                if (
                    entry[2] is token_or_handler
                    or (isinstance(token_or_handler, int) and entry[1] == token_or_handler)
                ):
                    entries.remove(entry)
                    removed = True
            if not entries:
                del self._handlers[event]
        return removed

    def unsubscribe_all(self, event: Optional[str] = None) -> int:
        """退订全部（event 为 None）或某事件的全部处理器，返回退订条数。"""
        if event is None:
            count = sum(len(e) for e in self._handlers.values())
            self._handlers.clear()
            return count
        entries = self._handlers.pop(event, [])
        return len(entries)

    @property
    def handler_count(self) -> int:
        """当前注册的处理器总数。"""
        return sum(len(e) for e in self._handlers.values())
