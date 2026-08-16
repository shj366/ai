from __future__ import annotations

import asyncio

from typing import TYPE_CHECKING, Any

from pydantic_ai import CancellationToken

if TYPE_CHECKING:
    from collections.abc import Callable

_END = object()


class ActiveChatRun:
    """进程内对话生成任务"""

    def __init__(self) -> None:
        self.cancellation_token = CancellationToken()
        self.subscribers: set[asyncio.Queue[Any]] = set()
        self.task: asyncio.Task[None] | None = None
        self.events: list[Any] = []
        self.done = False
        self.encode_event: Callable[[Any], str] | None = None
        self.media_type: str | None = None
        self.response_headers: dict[str, str] | None = None

    def publish(self, item: Any) -> None:
        """
        写入事件日志并向当前订阅者广播

        :param item: 协议事件或结束标记
        :return:
        """
        if item is _END:
            self.done = True
        else:
            self.events.append(item)
        for queue in list(self.subscribers):
            queue.put_nowait(item)

    def subscribe(self, *, after_id: int = 0) -> asyncio.Queue[Any]:
        """
        订阅生成事件，先回放 after_id 之后的日志再接收实时事件

        :param after_id: 已接收的最后一个事件 ID
        :return:
        """
        queue: asyncio.Queue[Any] = asyncio.Queue()
        for event in self.events[max(after_id, 0) :]:
            queue.put_nowait(event)
        if self.done:
            queue.put_nowait(_END)
        else:
            self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Any]) -> None:
        """
        取消订阅

        :param queue: 订阅队列
        :return:
        """
        self.subscribers.discard(queue)


_runs: dict[str, ActiveChatRun] = {}


def get_active_run(conversation_id: str) -> ActiveChatRun | None:
    """
    获取对话进行中的生成任务

    :param conversation_id: 对话 ID
    :return:
    """
    run = _runs.get(conversation_id)
    if run is None or run.task is None or run.task.done():
        return None
    return run


def has_active_run(conversation_id: str) -> bool:
    """
    对话是否有进行中的生成任务

    :param conversation_id: 对话 ID
    :return:
    """
    return get_active_run(conversation_id) is not None


def register_run(conversation_id: str) -> ActiveChatRun:
    """
    注册对话生成任务

    :param conversation_id: 对话 ID
    :return:
    """
    existing = get_active_run(conversation_id)
    if existing is not None:
        return existing
    run = ActiveChatRun()
    _runs[conversation_id] = run
    return run


def discard_run(conversation_id: str, run: ActiveChatRun) -> None:
    """
    移除已结束的生成任务

    :param conversation_id: 对话 ID
    :param run: 待移除的生成任务
    :return:
    """
    current = _runs.get(conversation_id)
    if current is run:
        _runs.pop(conversation_id, None)


def request_stop_run(conversation_id: str) -> bool:
    """
    请求停止对话生成

    :param conversation_id: 对话 ID
    :return:
    """
    run = get_active_run(conversation_id)
    if run is None:
        return False
    run.cancellation_token.cancel()
    return True


def get_run_end_sentinel() -> object:
    """获取生成流结束标记"""
    return _END
