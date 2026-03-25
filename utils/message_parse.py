from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypedDict

from pydantic_ai import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    UserPromptPart,
)
from pydantic_core import to_jsonable_python

from backend.common.exception import errors
from backend.plugin.ai.enums import AIChatMessageRoleType
from backend.utils.timezone import timezone


class ChatMessage(TypedDict):
    """发送给浏览器的消息格式"""

    message_id: int | None
    message_index: int
    role: AIChatMessageRoleType
    timestamp: str
    content: str
    conversation_id: str | None
    is_error: bool
    error_message: str | None
    structured_data: Any | None


@dataclass(slots=True)
class ChatTranscriptItem:
    """聊天转录项"""

    message_id: int | None
    message_index: int
    model_message_index: int
    role: AIChatMessageRoleType
    timestamp: str
    content: str
    conversation_id: str | None
    is_error: bool = False
    error_message: str | None = None
    structured_data: Any | None = None

    def to_chat_message(self) -> ChatMessage:
        return {
            'message_id': self.message_id,
            'message_index': self.message_index,
            'role': self.role,
            'timestamp': self.timestamp,
            'content': self.content,
            'conversation_id': self.conversation_id,
            'is_error': self.is_error,
            'error_message': self.error_message,
            'structured_data': self.structured_data,
        }


def make_chat_message(
    *,
    message_id: int | None = None,
    message_index: int,
    role: AIChatMessageRoleType,
    content: str,
    timestamp: datetime | None = None,
    conversation_id: str | None = None,
    is_error: bool = False,
    error_message: str | None = None,
    structured_data: Any | None = None,
) -> ChatMessage:
    """
    构造前端标准消息结构

    :param message_index: 前端展示消息索引
    :param message_id: 消息 ID
    :param role: 消息角色
    :param content: 消息内容
    :param timestamp: 消息时间
    :param conversation_id: 会话 ID
    :param is_error: 是否为错误消息
    :param error_message: 错误信息
    :param structured_data: 结构化数据
    :return:
    """
    return {
        'message_id': message_id,
        'message_index': message_index,
        'role': role,
        'timestamp': (timestamp or timezone.now()).isoformat(),
        'content': content,
        'conversation_id': conversation_id,
        'is_error': is_error,
        'error_message': error_message,
        'structured_data': structured_data,
    }


def to_chat_message(
    message: ModelMessage,
    *,
    message_id: int | None = None,
    message_index: int,
    conversation_id: str | None = None,
) -> ChatMessage:
    """
    将单条模型消息转换为单条前端消息

    该函数仅适用于一条 `ModelMessage` 对应一条展示消息的场景。

    :param message: 模型消息
    :param message_id: 消息 ID
    :param message_index: 前端展示消息索引
    :param conversation_id: 会话 ID
    :return:
    """
    metadata = message.metadata or {}
    is_error = bool(metadata.get('is_error', False))
    error_message = metadata.get('error_message')
    structured_data = metadata.get('structured_data')
    if error_message is not None:
        error_message = str(error_message)

    first_part = message.parts[0]
    if isinstance(message, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            assert isinstance(first_part.content, str)
            return make_chat_message(
                message_index=message_index,
                message_id=message_id,
                role=AIChatMessageRoleType.user,
                timestamp=first_part.timestamp,
                content=first_part.content,
                conversation_id=conversation_id,
                is_error=is_error,
                error_message=error_message,
                structured_data=structured_data,
            )
    elif isinstance(message, ModelResponse) and isinstance(first_part, TextPart):
        return make_chat_message(
            message_index=message_index,
            message_id=message_id,
            role=AIChatMessageRoleType.model,
            timestamp=message.timestamp,
            content=first_part.content,
            conversation_id=conversation_id,
            is_error=is_error,
            error_message=error_message,
            structured_data=structured_data,
        )
    raise errors.NotFoundError(msg=f'消息类型错误: {message}')


def to_chat_messages_by_parts(
    message: ModelMessage,
    *,
    message_id: int | None = None,
    start_message_index: int,
    conversation_id: str | None = None,
) -> list[ChatMessage]:
    """
    按消息分片展开模型消息

    一个 `ModelResponse` 可能同时包含多个可展示分片，例如 thinking 和 text，
    该函数会将其展开为多条连续的前端消息。

    :param message: 模型消息
    :param message_id: 消息 ID
    :param start_message_index: 起始前端展示消息索引
    :param conversation_id: 会话 ID
    :return:
    """
    metadata = message.metadata or {}
    is_error = bool(metadata.get('is_error', False))
    error_message = metadata.get('error_message')
    structured_data = metadata.get('structured_data')
    if error_message is not None:
        error_message = str(error_message)

    if isinstance(message, ModelRequest):
        first_part = message.parts[0]
        if isinstance(first_part, UserPromptPart) and isinstance(first_part.content, str):
            return [
                make_chat_message(
                    message_index=start_message_index,
                    message_id=message_id,
                    role=AIChatMessageRoleType.user,
                    timestamp=first_part.timestamp,
                    content=first_part.content,
                    conversation_id=conversation_id,
                    is_error=is_error,
                    error_message=error_message,
                    structured_data=structured_data,
                )
            ]
        raise errors.NotFoundError(msg=f'消息类型错误: {message}')

    if not isinstance(message, ModelResponse):
        raise errors.NotFoundError(msg=f'消息类型错误: {message}')

    items: list[ChatMessage] = []
    next_index = start_message_index
    for part in message.parts:
        if isinstance(part, ThinkingPart):
            items.append(
                make_chat_message(
                    message_index=next_index,
                    message_id=message_id,
                    role=AIChatMessageRoleType.thinking,
                    timestamp=message.timestamp,
                    content=part.content,
                    conversation_id=conversation_id,
                    is_error=is_error,
                    error_message=error_message,
                    structured_data=structured_data,
                )
            )
            next_index += 1
        elif isinstance(part, TextPart):
            items.append(
                make_chat_message(
                    message_index=next_index,
                    message_id=message_id,
                    role=AIChatMessageRoleType.model,
                    timestamp=message.timestamp,
                    content=part.content,
                    conversation_id=conversation_id,
                    is_error=is_error,
                    error_message=error_message,
                    structured_data=structured_data,
                )
            )
            next_index += 1

    if items:
        return items
    raise errors.NotFoundError(msg=f'消息类型错误: {message}')


def build_chat_transcript(
    messages: Sequence[ModelMessage],
    *,
    conversation_id: str | None = None,
    message_ids: Sequence[int | None] | None = None,
) -> list[ChatTranscriptItem]:
    """
    构建聊天转录列表

    返回结果同时保留前端展示消息索引和底层模型消息索引，
    以便在展示层消息与底层消息之间进行映射。

    :param messages: 模型消息序列
    :param conversation_id: 会话 ID
    :param message_ids: 消息 ID 序列
    :return:
    """
    transcript: list[ChatTranscriptItem] = []
    for model_message_index, message in enumerate(messages):
        try:
            parsed_messages = to_chat_messages_by_parts(
                message,
                message_id=message_ids[model_message_index] if message_ids else None,
                start_message_index=len(transcript),
                conversation_id=conversation_id,
            )
        except errors.NotFoundError:
            parsed_messages = []
        transcript.extend(
            ChatTranscriptItem(
                message_id=parsed_message['message_id'],
                message_index=parsed_message['message_index'],
                model_message_index=model_message_index,
                role=parsed_message['role'],
                timestamp=parsed_message['timestamp'],
                content=parsed_message['content'],
                conversation_id=parsed_message['conversation_id'],
                is_error=parsed_message['is_error'],
                error_message=parsed_message['error_message'],
                structured_data=parsed_message['structured_data'],
            )
            for parsed_message in parsed_messages
        )
    return transcript


def to_chat_messages(
    messages: Sequence[ModelMessage],
    *,
    conversation_id: str | None = None,
    message_ids: Sequence[int | None] | None = None,
) -> list[ChatMessage]:
    """
    将模型消息序列转换为前端消息列表

    :param messages: 模型消息序列
    :param conversation_id: 会话 ID
    :param message_ids: 消息 ID 序列
    :return:
    """
    return [
        item.to_chat_message()
        for item in build_chat_transcript(messages, conversation_id=conversation_id, message_ids=message_ids)
    ]


def get_chat_transcript_item(
    messages: Sequence[ModelMessage],
    *,
    message_index: int,
    conversation_id: str | None = None,
) -> ChatTranscriptItem:
    """
    通过前端展示消息索引获取聊天转录项

    :param messages: 模型消息序列
    :param message_index: 前端展示消息索引
    :param conversation_id: 会话 ID
    :return:
    """
    transcript = build_chat_transcript(messages, conversation_id=conversation_id)
    if message_index < 0 or message_index >= len(transcript):
        raise errors.NotFoundError(msg='聊天消息不存在')
    return transcript[message_index]


def truncate_model_messages_by_index(
    messages: Sequence[ModelMessage],
    *,
    message_index: int,
    conversation_id: str | None = None,
) -> list[ModelMessage]:
    """
    根据前端展示消息索引截断模型消息序列

    返回目标消息之前的所有模型消息，用于构造前置上下文。

    :param messages: 模型消息序列
    :param message_index: 前端展示消息索引
    :param conversation_id: 会话 ID
    :return:
    """
    target_item = get_chat_transcript_item(messages, message_index=message_index, conversation_id=conversation_id)
    return list(messages[: target_item.model_message_index])


def delete_model_message_by_index(
    messages: Sequence[ModelMessage],
    *,
    message_index: int,
    conversation_id: str | None = None,
) -> list[ModelMessage]:
    """
    根据前端展示消息索引删除对应的模型消息

    删除目标是前端展示消息索引映射后的整条底层模型消息。

    :param messages: 模型消息序列
    :param message_index: 前端展示消息索引
    :param conversation_id: 会话 ID
    :return:
    """
    target_item = get_chat_transcript_item(messages, message_index=message_index, conversation_id=conversation_id)
    remaining_messages = list(messages)
    del remaining_messages[target_item.model_message_index]
    return remaining_messages


def serialize_model_messages(messages: Sequence[ModelMessage]) -> list[dict[str, Any]]:
    payload = to_jsonable_python(list(messages))
    assert isinstance(payload, list)
    return payload
