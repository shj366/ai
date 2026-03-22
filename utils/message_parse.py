from datetime import datetime
from typing import Literal, TypedDict

from pydantic_ai import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from backend.common.exception import errors
from backend.utils.timezone import timezone


class ChatMessage(TypedDict):
    """发送给浏览器的消息格式"""

    role: Literal['user', 'model']
    timestamp: str
    content: str


def make_chat_message(
    *, role: Literal['user', 'model'], content: str, timestamp: datetime | None = None
) -> ChatMessage:
    return {
        'role': role,
        'timestamp': (timestamp or timezone.now()).isoformat(),
        'content': content,
    }


def to_chat_message(message: ModelMessage) -> ChatMessage:
    first_part = message.parts[0]
    if isinstance(message, ModelRequest):
        if isinstance(first_part, UserPromptPart):
            assert isinstance(first_part.content, str)
            return make_chat_message(role='user', timestamp=first_part.timestamp, content=first_part.content)
    elif isinstance(message, ModelResponse) and isinstance(first_part, TextPart):
        return make_chat_message(role='model', timestamp=message.timestamp, content=first_part.content)
    raise errors.NotFoundError(msg=f'消息类型错误: {message}')
