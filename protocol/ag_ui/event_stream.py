from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, TypeAlias

import anyio

from ag_ui.core import BaseEvent, RunAgentInput, RunErrorEvent
from pydantic_ai import Agent, AgentRunResult, BinaryImage, ModelRequest, ModelResponse
from pydantic_ai.ui.ag_ui import AGUIAdapter
from starlette.responses import StreamingResponse

from backend.plugin.ai.dataclasses import ChatAgentDeps

ChatModelMessage: TypeAlias = ModelRequest | ModelResponse
ChatAgentOutput: TypeAlias = BinaryImage | str
ChatAgent: TypeAlias = Agent[ChatAgentDeps, ChatAgentOutput]


class _StreamLifecycle:
    """流式回调生命周期"""

    def __init__(
        self,
        *,
        on_complete: Callable[[AgentRunResult[Any]], Awaitable[None]],
        on_run_error: Callable[[str], Awaitable[None]],
    ) -> None:
        self.on_complete = on_complete
        self.on_run_error = on_run_error
        self.run_finished = False
        self.error_handled = False

    async def complete(self, result: AgentRunResult[Any]) -> None:
        """幂等执行完成回调"""
        if self.run_finished or self.error_handled:
            return
        await self.on_complete(result)
        self.run_finished = True

    async def handle_error(self, message: str) -> None:
        """幂等执行错误回调"""
        if self.run_finished or self.error_handled:
            return
        await self.on_run_error(message)
        self.error_handled = True


async def _stream_with_lifecycle(
    *,
    event_stream: AsyncIterator[BaseEvent],
    lifecycle: _StreamLifecycle,
    on_finish: Callable[[], Awaitable[None]] | None,
) -> AsyncIterator[BaseEvent]:
    """消费事件流并保证中断清理"""
    try:
        async for event in event_stream:
            if isinstance(event, RunErrorEvent):
                await lifecycle.handle_error(event.message or '')
            yield event
    finally:
        with anyio.CancelScope(shield=True):
            try:
                if not lifecycle.run_finished and not lifecycle.error_handled:
                    await lifecycle.handle_error('生成已中断')
            finally:
                try:
                    aclose = getattr(event_stream, 'aclose', None)
                    if aclose is not None:
                        await aclose()
                finally:
                    if on_finish:
                        await on_finish()


async def ag_ui_event_encoder(stream: AsyncIterator[BaseEvent]) -> AsyncIterator[str]:
    """
    AG-UI 事件流编码器

    :param stream: AG-UI 事件流
    :return:
    """
    async for event in stream:
        yield f'data: {event.model_dump_json(by_alias=True, exclude_none=True)}\n\n'


def build_streaming_response(
    *,
    user_id: int,
    agent: ChatAgent,
    run_input: RunAgentInput,
    accept: str | None,
    message_history: list[ChatModelMessage],
    on_complete: Callable[[AgentRunResult[Any]], Awaitable[None]],
    on_run_error: Callable[[str], Awaitable[None]],
    on_finish: Callable[[], Awaitable[None]] | None = None,
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
    :param on_finish: 流结束回调
    :return:
    """
    adapter = AGUIAdapter(
        agent=agent,
        run_input=run_input,
        accept=accept,
        allow_uploaded_files=True,
        preserve_file_data=True,
    )
    lifecycle = _StreamLifecycle(on_complete=on_complete, on_run_error=on_run_error)
    event_stream = adapter.run_stream(
        deps=ChatAgentDeps(user_id=user_id),
        message_history=message_history,
        on_complete=lifecycle.complete,
    )
    event_stream_handler = adapter.build_event_stream()
    response = StreamingResponse(
        ag_ui_event_encoder(
            _stream_with_lifecycle(
                event_stream=event_stream,
                lifecycle=lifecycle,
                on_finish=on_finish,
            )
        ),
        headers=event_stream_handler.response_headers,
        media_type=event_stream_handler.content_type,
    )
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Cache-Control'] = 'no-cache'
    return response
