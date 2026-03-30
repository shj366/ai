from collections.abc import Sequence

from pydantic_ai import (
    AudioUrl,
    BinaryContent,
    DocumentUrl,
    FilePart,
    ImageUrl,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    UserPromptPart,
    VideoUrl,
)

from backend.plugin.ai.enums import AIChatAttachmentSourceType, AIChatAttachmentType, AIMessageRoleType
from backend.plugin.ai.schema.message import GetAIMessageAttachmentDetail, GetAIMessageDetail
from backend.utils.timezone import timezone


def get_attachment_type(content: BinaryContent) -> AIChatAttachmentType:
    """
    获取二进制附件类型

    :param content: 二进制内容
    :return:
    """
    if content.is_image:
        return AIChatAttachmentType.image
    if content.is_audio:
        return AIChatAttachmentType.audio
    if content.is_video:
        return AIChatAttachmentType.video
    return AIChatAttachmentType.document


def build_attachment_detail(
    attachment: ImageUrl | AudioUrl | VideoUrl | DocumentUrl | BinaryContent,
) -> GetAIMessageAttachmentDetail:
    """
    构建消息附件详情

    :param attachment: 附件
    :return:
    """
    if isinstance(attachment, ImageUrl):
        return GetAIMessageAttachmentDetail(
            type=AIChatAttachmentType.image,
            source_type=AIChatAttachmentSourceType.url,
            mime_type=attachment.media_type,
            url=attachment.url,
        )
    if isinstance(attachment, AudioUrl):
        return GetAIMessageAttachmentDetail(
            type=AIChatAttachmentType.audio,
            source_type=AIChatAttachmentSourceType.url,
            mime_type=attachment.media_type,
            url=attachment.url,
        )
    if isinstance(attachment, VideoUrl):
        return GetAIMessageAttachmentDetail(
            type=AIChatAttachmentType.video,
            source_type=AIChatAttachmentSourceType.url,
            mime_type=attachment.media_type,
            url=attachment.url,
        )
    if isinstance(attachment, DocumentUrl):
        return GetAIMessageAttachmentDetail(
            type=AIChatAttachmentType.document,
            source_type=AIChatAttachmentSourceType.url,
            mime_type=attachment.media_type,
            url=attachment.url,
        )
    return GetAIMessageAttachmentDetail(
        type=get_attachment_type(attachment),
        source_type=AIChatAttachmentSourceType.base64,
        mime_type=attachment.media_type,
        url=attachment.data_uri,
    )


def serialize_messages(  # noqa: C901
    messages: Sequence[ModelMessage],
    *,
    conversation_id: str | None = None,
    message_ids: Sequence[int | None] | None = None,
) -> list[GetAIMessageDetail]:
    """
    序列化模型消息

    :param messages: 模型消息序列
    :param conversation_id: 对话 ID
    :param message_ids: 消息 ID 序列
    :return:
    """
    parsed_messages: list[GetAIMessageDetail] = []
    for model_message_index, message in enumerate(messages):
        message_id = message_ids[model_message_index] if message_ids else None

        if isinstance(message, ModelRequest) and message.parts:
            first_part = message.parts[0]
            if isinstance(first_part, UserPromptPart):
                attachments: list[GetAIMessageAttachmentDetail] = []
                text_parts: list[str] = []
                if isinstance(first_part.content, str):
                    text_parts.append(first_part.content)
                else:
                    for item in first_part.content:
                        if isinstance(item, str):
                            text_parts.append(item)
                            continue
                        if isinstance(item, (ImageUrl, AudioUrl, VideoUrl, DocumentUrl, BinaryContent)):
                            attachments.append(build_attachment_detail(item))
                parsed_messages.append(
                    GetAIMessageDetail(
                        message_id=message_id,
                        message_index=len(parsed_messages),
                        role=AIMessageRoleType.user,
                        timestamp=first_part.timestamp.isoformat(),
                        content=' '.join(text_parts).strip(),
                        attachments=attachments,
                        conversation_id=conversation_id,
                    )
                )
            continue

        if not isinstance(message, ModelResponse):
            continue

        timestamp = message.timestamp.isoformat() if message.timestamp else timezone.now().isoformat()
        for part in message.parts:
            role: AIMessageRoleType | None = None
            content = ''

            if isinstance(part, ThinkingPart):
                role = AIMessageRoleType.thinking
                content = part.content
            elif isinstance(part, TextPart):
                role = AIMessageRoleType.model
                content = part.content
            if role is None:
                if isinstance(part, FilePart):
                    parsed_messages.append(
                        GetAIMessageDetail(
                            message_id=message_id,
                            message_index=len(parsed_messages),
                            role=AIMessageRoleType.model,
                            timestamp=timestamp,
                            content='',
                            attachments=[build_attachment_detail(part.content)],
                            conversation_id=conversation_id,
                        )
                    )
                continue

            parsed_messages.append(
                GetAIMessageDetail(
                    message_id=message_id,
                    message_index=len(parsed_messages),
                    role=role,
                    timestamp=timestamp,
                    content=content,
                    attachments=[],
                    conversation_id=conversation_id,
                )
            )

    return parsed_messages
