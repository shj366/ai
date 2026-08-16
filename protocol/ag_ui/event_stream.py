import asyncio
import time

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, TypeAlias

import anyio

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent
from pydantic_ai import (
    Agent,
    AgentRunResult,
    BinaryImage,
    CancellationToken,
    ModelRequest,
    ModelResponse,
    RunCancelled,
    capture_run_messages,
)
from pydantic_ai.ui.ag_ui import AGUIAdapter
from starlette.responses import Response, StreamingResponse

from backend.common.log import log
from backend.plugin.ai.chat.runs import (
    ActiveChatRun,
    discard_run,
    get_active_run,
    get_run_end_sentinel,
    register_run,
)
from backend.plugin.ai.dataclasses import ChatAgentDeps

ChatModelMessage: TypeAlias = ModelRequest | ModelResponse
ChatAgentOutput: TypeAlias = BinaryImage | str
ChatAgent: TypeAlias = Agent[ChatAgentDeps, ChatAgentOutput]

_SNAPSHOT_INTERVAL_SECONDS = 2.0


class _StreamLifecycle:
    """流式回调生命周期"""

    def __init__(
        self,
        *,
        on_complete: Callable[[AgentRunResult[Any]], Awaitable[None]],
        on_run_error: Callable[[str, list[ChatModelMessage]], Awaitable[None]],
        on_interrupted: Callable[[list[ChatModelMessage]], Awaitable[None]],
    ) -> None:
        self.on_complete = on_complete
        self.on_run_error = on_run_error
        self.on_interrupted = on_interrupted
        self.run_finished = False
        self.error_message: str | None = None

    async def complete(self, result: AgentRunResult[Any]) -> None:
        """
        幂等执行完成回调

        :param result: 代理运行结果
        :return:
        """
        if self.run_finished or self.error_message is not None:
            return
        try:
            await self.on_complete(result)
        except Exception as exc:
            # 完成回调失败时走错误终态，避免再被当成客户端中断导致 pending 锁死或状态打架
            if self.error_message is None:
                self.error_message = str(exc) or '完成回调失败'
            raise
        else:
            self.run_finished = True

    def record_error(self, message: str) -> None:
        """
        记录首个运行错误，等待原生消息状态完成收敛

        :param message: 错误信息
        :return:
        """
        if self.run_finished or self.error_message is not None:
            return
        self.error_message = message

    async def cancel(self, cancelled: RunCancelled) -> None:
        """
        持久化第一方取消的本轮增量消息

        :param cancelled: 第一方取消结果
        :return:
        """
        if self.run_finished:
            return
        await self.on_interrupted(list(cancelled.new_messages()))
        self.run_finished = True

    async def finalize(self, messages: list[ChatModelMessage]) -> None:
        """
        在底层流关闭后持久化失败或中断状态

        :param messages: 当前轮原生消息
        :return:
        """
        if self.run_finished:
            return
        try:
            if self.error_message is not None:
                await self.on_run_error(self.error_message, messages)
            else:
                await self.on_interrupted(messages)
        finally:
            # 无论落库成败都标记结束，防止重复 finalize
            self.run_finished = True


def _extract_current_run_messages(
    *,
    captured_messages: Sequence[ChatModelMessage],
    message_history: Sequence[ChatModelMessage],
) -> list[ChatModelMessage]:
    """
    提取当前轮原生消息

    capture_run_messages 仅捕获本 run；优先按 run_id 过滤。
    无 run_id 时回退为全部捕获结果，避免中断落库丢消息。

    :param captured_messages: 本次运行捕获的模型消息
    :param message_history: 传入模型的历史消息
    :return:
    """
    if not captured_messages:
        return []
    history_run_ids = {message.run_id for message in message_history if message.run_id is not None}
    current_run_id = next(
        (
            message.run_id
            for message in reversed(captured_messages)
            if message.run_id is not None and message.run_id not in history_run_ids
        ),
        None,
    )
    if current_run_id is None:
        return list(captured_messages)
    return [message for message in captured_messages if message.run_id == current_run_id]


async def _close_event_stream(*, event_stream: AsyncIterator[BaseEvent]) -> None:
    """
    在当前任务中关闭 Pydantic AI 官方事件流

    :param event_stream: 官方事件流
    :return:
    """
    aclose = getattr(event_stream, 'aclose', None)
    if aclose is None:
        return
    try:
        await aclose()
    except BaseException as exc:
        # 清理异常不能覆盖模型异常或客户端取消，也不能留下未回收的后台任务
        log.warning('关闭 Pydantic AI 事件流失败: {}', exc)


class _CancellationBoundAgent:
    """向 AG-UI 适配器注入 CancellationToken，不改动共享 Agent"""

    def __init__(self, agent: ChatAgent, token: CancellationToken) -> None:
        object.__setattr__(self, '_agent', agent)
        object.__setattr__(self, '_token', token)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)

    def run_stream_events(self, *args: Any, **kwargs: Any) -> Any:
        """
        注入取消令牌后转发到原 Agent

        :param args: 原 Agent 位置参数
        :param kwargs: 原 Agent 关键字参数
        :return:
        """
        kwargs.setdefault('cancellation_token', self._token)
        return self._agent.run_stream_events(*args, **kwargs)


async def _observe_native_events(
    *,
    event_stream: AsyncIterator[BaseEvent],
    message_history: Sequence[ChatModelMessage],
    lifecycle: _StreamLifecycle,
    on_finish: Callable[[], Awaitable[None]] | None,
    on_snapshot: Callable[[list[ChatModelMessage]], Awaitable[None]] | None = None,
) -> AsyncIterator[BaseEvent]:
    """
    观察 Pydantic AI 原生事件并执行持久化生命周期回调

    :param event_stream: 官方协议事件流
    :param message_history: 传入模型的历史消息
    :param lifecycle: 流式回调生命周期
    :param on_finish: 流结束回调
    :param on_snapshot: 增量快照回调
    :return:
    """
    current_run_messages: list[ChatModelMessage] = []
    last_snapshot_at = 0.0
    try:
        try:
            with capture_run_messages() as captured_messages:
                try:
                    async for event in event_stream:
                        if isinstance(event, RunErrorEvent):
                            lifecycle.record_error(event.message or '')
                        yield event
                        if on_snapshot is None:
                            continue
                        now = time.monotonic()
                        if now - last_snapshot_at < _SNAPSHOT_INTERVAL_SECONDS:
                            continue
                        last_snapshot_at = now
                        snapshot_messages = _extract_current_run_messages(
                            captured_messages=captured_messages,
                            message_history=message_history,
                        )
                        if snapshot_messages:
                            await on_snapshot(snapshot_messages)
                finally:
                    await _close_event_stream(event_stream=event_stream)
                    current_run_messages.extend(
                        _extract_current_run_messages(
                            captured_messages=captured_messages,
                            message_history=message_history,
                        )
                    )
        except ValueError as exc:
            if 'created in a different Context' not in str(exc):
                raise
            log.warning('Pydantic AI 消息捕获上下文已在其他任务关闭: {}', exc)
    finally:
        # 屏蔽取消：任务取消时仍完成落库/回调，避免状态与资源不一致
        with anyio.CancelScope(shield=True):
            try:
                await lifecycle.finalize(current_run_messages)
            finally:
                if on_finish:
                    await on_finish()


async def _produce_run_events(
    *,
    conversation_id: str,
    run: ActiveChatRun,
    event_stream: AsyncIterator[BaseEvent],
    message_history: list[ChatModelMessage],
    lifecycle: _StreamLifecycle,
    on_finish: Callable[[], Awaitable[None]] | None,
    on_snapshot: Callable[[list[ChatModelMessage]], Awaitable[None]] | None,
) -> None:
    """
    在后台消费模型事件，不随 HTTP 断开取消

    :param conversation_id: 对话 ID
    :param run: 进行中的生成任务
    :param event_stream: 官方协议事件流
    :param message_history: 传入模型的历史消息
    :param lifecycle: 流式回调生命周期
    :param on_finish: 流结束回调
    :param on_snapshot: 增量快照回调
    :return:
    """
    try:
        async for event in _observe_native_events(
            event_stream=event_stream,
            message_history=message_history,
            lifecycle=lifecycle,
            on_finish=on_finish,
            on_snapshot=on_snapshot,
        ):
            run.publish(event)
    except Exception as exc:
        log.exception(f'后台聊天生成任务异常 conversation_id={conversation_id}: {exc}')
    finally:
        run.publish(get_run_end_sentinel())
        discard_run(conversation_id, run)


async def _encode_run_events(
    *,
    encode_event: Callable[[BaseEvent], str],
    run: ActiveChatRun,
    after_id: int,
) -> AsyncIterator[str]:
    """
    订阅并编码带 SSE id 的可恢复事件流

    :param encode_event: 协议事件编码器
    :param run: 进行中的生成任务
    :param after_id: 已接收的最后一个事件 ID
    :return:
    """
    queue = run.subscribe(after_id=after_id)
    end_sentinel = get_run_end_sentinel()
    event_id = after_id
    try:
        while True:
            item = await queue.get()
            if item is end_sentinel:
                break
            event_id += 1
            encoded = encode_event(item)
            if encoded.startswith('id:'):
                yield encoded
                continue
            yield f'id: {event_id}\n{encoded}'
    finally:
        run.unsubscribe(queue)


def build_streaming_response(
    *,
    user_id: int,
    agent: ChatAgent,
    run_input: RunAgentInput,
    accept: str | None,
    message_history: list[ChatModelMessage],
    on_complete: Callable[[AgentRunResult[Any]], Awaitable[None]],
    on_run_error: Callable[[str, list[ChatModelMessage]], Awaitable[None]],
    on_interrupted: Callable[[list[ChatModelMessage]], Awaitable[None]],
    on_finish: Callable[[], Awaitable[None]] | None = None,
    conversation_id: str | None = None,
    on_snapshot: Callable[[list[ChatModelMessage]], Awaitable[None]] | None = None,
) -> StreamingResponse:
    """
    运行聊天代理并返回流式响应

    :param user_id: 用户 ID
    :param agent: 聊天代理
    :param run_input: 运行参数
    :param accept: Accept 请求头
    :param message_history: 消息历史
    :param on_complete: 完成回调
    :param on_run_error: 运行失败回调
    :param on_interrupted: 运行中断回调
    :param on_finish: 流结束回调
    :param conversation_id: 对话 ID，用于后台任务登记
    :param on_snapshot: 增量快照回调
    :return:
    """
    resolved_conversation_id = conversation_id or run_input.thread_id
    active_run = get_active_run(resolved_conversation_id)
    if active_run is None:
        active_run = register_run(resolved_conversation_id)
        try:
            adapter = AGUIAdapter(
                agent=_CancellationBoundAgent(agent, active_run.cancellation_token),
                run_input=run_input,
                accept=accept,
                allow_uploaded_files=True,
                preserve_file_data=True,
            )
            lifecycle = _StreamLifecycle(
                on_complete=on_complete,
                on_run_error=on_run_error,
                on_interrupted=on_interrupted,
            )
            event_stream_handler = adapter.build_event_stream()
            active_run.encode_event = event_stream_handler.encode_event
            active_run.media_type = event_stream_handler.content_type
            active_run.response_headers = dict(event_stream_handler.response_headers or {})
            event_stream = adapter.run_stream(
                deps=ChatAgentDeps(user_id=user_id),
                message_history=message_history,
                on_complete=lifecycle.complete,
                on_cancel=lifecycle.cancel,
            )
            active_run.task = asyncio.create_task(
                _produce_run_events(
                    conversation_id=resolved_conversation_id,
                    run=active_run,
                    event_stream=event_stream,
                    message_history=message_history,
                    lifecycle=lifecycle,
                    on_finish=on_finish,
                    on_snapshot=on_snapshot,
                ),
                name=f'ai-chat-run-{resolved_conversation_id}',
            )
        except BaseException:
            discard_run(resolved_conversation_id, active_run)
            raise
    return _build_subscriber_response(run=active_run, after_id=0)


def parse_stream_resume_after_id(*, last_event_id: str | None, after: str | None) -> int:
    """
    解析可恢复流的起始事件偏移

    :param last_event_id: Last-Event-ID 请求头
    :param after: 查询参数中的事件偏移
    :return:
    """
    raw = last_event_id or after
    if raw is None or not raw.isdigit():
        return 0
    return int(raw)


def build_resume_streaming_response(
    *,
    conversation_id: str,
    after_id: int = 0,
) -> Response:
    """
    续订进行中的对话生成流

    :param conversation_id: 对话 ID
    :param after_id: 已接收的最后一个事件 ID
    :return:
    """
    active_run = get_active_run(conversation_id)
    if active_run is None:
        return Response(status_code=204)
    return _build_subscriber_response(run=active_run, after_id=after_id)


def _build_subscriber_response(*, run: ActiveChatRun, after_id: int) -> StreamingResponse:
    """
    构建订阅者 SSE 响应

    :param run: 进行中的生成任务
    :param after_id: 已接收的最后一个事件 ID
    :return:
    """
    encode_event = run.encode_event
    if encode_event is None:
        raise RuntimeError('生成任务缺少事件编码器')
    response = StreamingResponse(
        _encode_run_events(encode_event=encode_event, run=run, after_id=after_id),
        headers=run.response_headers or {},
        media_type=run.media_type or 'text/event-stream',
    )
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache'
    return response
