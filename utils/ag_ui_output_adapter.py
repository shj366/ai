import json

from base64 import b64encode
from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypeAlias, cast

from ag_ui.core import FunctionCall, InputContentDataSource, InputContentUrlSource, TextInputContent, ToolCall
from pydantic_ai import (
    AudioUrl,
    BinaryContent,
    CachePoint,
    DocumentUrl,
    FilePart,
    ImageUrl,
    InstructionPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextContent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UploadedFile,
    UserPromptPart,
    VideoUrl,
)
from pydantic_core import to_jsonable_python

from backend.plugin.ai.schema.ag_ui import (
    AIChatActivityMessageDetail,
    AIChatAssistantFileActivityContentSchemaBase,
    AIChatAssistantMessageDetail,
    AIChatAudioInputContentSchemaBase,
    AIChatBinaryInputContentSchemaBase,
    AIChatDocumentInputContentSchemaBase,
    AIChatImageInputContentSchemaBase,
    AIChatInputContentMetadataSchemaBase,
    AIChatMessagesSnapshotDetail,
    AIChatReasoningMessageDetail,
    AIChatRequestInstructionActivityContentSchemaBase,
    AIChatSnapshotMessageDetail,
    AIChatSystemMessageDetail,
    AIChatToolMessageDetail,
    AIChatUserMessageParam,
    AIChatVendorMetadataSchemaBase,
    AIChatVideoInputContentSchemaBase,
)

SnapshotMessage: TypeAlias = (
    AIChatUserMessageParam
    | AIChatAssistantMessageDetail
    | AIChatSystemMessageDetail
    | AIChatToolMessageDetail
    | AIChatActivityMessageDetail
    | AIChatReasoningMessageDetail
)
AttachmentInputContent: TypeAlias = (
    AIChatImageInputContentSchemaBase
    | AIChatAudioInputContentSchemaBase
    | AIChatVideoInputContentSchemaBase
    | AIChatDocumentInputContentSchemaBase
    | AIChatBinaryInputContentSchemaBase
)
SnapshotInputContent: TypeAlias = TextInputContent | AttachmentInputContent
SnapshotMetaValue: TypeAlias = datetime | str | int | None
SnapshotInputContentItem: TypeAlias = (
    str | TextContent | ImageUrl | AudioUrl | VideoUrl | DocumentUrl | BinaryContent | UploadedFile | CachePoint
)


def serialize_tool_return_content(content: object) -> str:
    """
    序列化工具返回内容

    :param content: 工具返回内容
    :return:
    """
    if isinstance(content, str):
        return content
    return json.dumps(to_jsonable_python(content), ensure_ascii=False)


def build_vendor_metadata_schema(vendor_metadata: dict[str, Any] | None) -> AIChatVendorMetadataSchemaBase | None:
    """
    构建供应商元数据模型

    :param vendor_metadata: 供应商元数据
    :return:
    """
    if not vendor_metadata:
        return None
    filename = vendor_metadata.get('filename')
    if not isinstance(filename, str):
        return None
    return AIChatVendorMetadataSchemaBase(filename=filename)


def serialize_instruction_activity_text(
    part: InstructionPart | RetryPromptPart,
) -> str | list[dict[str, Any]]:
    """
    序列化请求指令活动内容

    :param part: 指令片段
    :return:
    """
    if isinstance(part.content, str):
        return part.content
    return cast('list[dict[str, Any]]', to_jsonable_python(part.content))


def build_input_content(
    attachment: ImageUrl | AudioUrl | VideoUrl | DocumentUrl | BinaryContent | UploadedFile,
) -> AttachmentInputContent:
    """
    构建 AG-UI 输入内容

    :param attachment: 附件内容
    :return:
    """
    if isinstance(attachment, UploadedFile):
        vendor_metadata = build_vendor_metadata_schema(attachment.vendor_metadata)
        filename = vendor_metadata.filename if vendor_metadata else None
        return AIChatBinaryInputContentSchemaBase(
            id=attachment.file_id,
            mime_type=attachment.media_type,
            filename=filename if isinstance(filename, str) else None,
            provider_name=attachment.provider_name,
            identifier=attachment.identifier,
            vendor_metadata=vendor_metadata,
        )

    vendor_metadata = build_vendor_metadata_schema(attachment.vendor_metadata)
    metadata = AIChatInputContentMetadataSchemaBase(
        id=attachment.identifier,
        vendor_metadata=vendor_metadata,
        filename=vendor_metadata.filename if vendor_metadata else None,
    )
    source: InputContentDataSource | InputContentUrlSource
    if isinstance(attachment, BinaryContent):
        source = InputContentDataSource(
            value=b64encode(attachment.data).decode(),
            mime_type=attachment.media_type,
        )
    else:
        source = InputContentUrlSource(value=attachment.url, mime_type=attachment.media_type)

    if isinstance(attachment, (ImageUrl,)) or (isinstance(attachment, BinaryContent) and attachment.is_image):
        return AIChatImageInputContentSchemaBase(source=source, metadata=metadata)
    if isinstance(attachment, (AudioUrl,)) or (isinstance(attachment, BinaryContent) and attachment.is_audio):
        return AIChatAudioInputContentSchemaBase(source=source, metadata=metadata)
    if isinstance(attachment, (VideoUrl,)) or (isinstance(attachment, BinaryContent) and attachment.is_video):
        return AIChatVideoInputContentSchemaBase(source=source, metadata=metadata)
    return AIChatDocumentInputContentSchemaBase(source=source, metadata=metadata)


def build_snapshot_message_id(*, message_id: int | None, message_index: int, suffix: str = '') -> str:
    """
    构建快照消息 ID

    :param message_id: 持久化消息 ID
    :param message_index: 消息索引
    :param suffix: 扩展后缀
    :return:
    """
    base_id = f'msg_{message_id if message_id is not None else message_index}'
    return f'{base_id}{suffix}'


def build_snapshot_input_content_list(
    *,
    content: Sequence[SnapshotInputContentItem],
) -> list[SnapshotInputContent]:
    """
    构建快照输入内容列表

    :param content: 内容列表
    :return:
    """
    snapshot_content: list[SnapshotInputContent] = []
    for item in content:
        if isinstance(item, str):
            snapshot_content.append(TextInputContent(text=item))
            continue
        if isinstance(item, TextContent):
            snapshot_content.append(TextInputContent(text=item.content))
            continue
        if isinstance(item, CachePoint):
            continue
        if isinstance(item, (ImageUrl, AudioUrl, VideoUrl, DocumentUrl, BinaryContent, UploadedFile)):
            snapshot_content.append(build_input_content(item))
    return snapshot_content


def serialize_request_message(
    *,
    message: ModelRequest,
    conversation_id: str | None,
    message_id: int | None,
    provider_id: int | None,
    model_id: str | None,
    message_index: int,
) -> SnapshotMessage | None:
    """
    序列化请求消息

    :param message: 请求消息
    :param conversation_id: 对话 ID
    :param message_id: 持久化消息 ID
    :param provider_id: 供应商 ID
    :param model_id: 模型 ID
    :param message_index: 消息索引
    :return:
    """
    if not message.parts:
        return None
    first_part = message.parts[0]
    created_time = first_part.timestamp
    message_meta: dict[str, SnapshotMetaValue] = {
        'conversation_id': conversation_id,
        'persisted_message_id': message_id,
        'provider_id': provider_id,
        'model_id': model_id,
        'created_time': created_time,
        'message_index': message_index,
        'message_type': 'normal',
    }
    if isinstance(first_part, UserPromptPart):
        content = (
            first_part.content
            if isinstance(first_part.content, str)
            else build_snapshot_input_content_list(content=first_part.content)
        )
        return AIChatUserMessageParam(
            id=build_snapshot_message_id(message_id=message_id, message_index=message_index),
            content=content,
            **message_meta,
        )
    if isinstance(first_part, SystemPromptPart):
        return AIChatSystemMessageDetail(
            id=build_snapshot_message_id(message_id=message_id, message_index=message_index),
            content=first_part.content,
            **message_meta,
        )
    if isinstance(first_part, (InstructionPart, RetryPromptPart)):
        part_created_time = getattr(first_part, 'timestamp', message.timestamp)
        return AIChatActivityMessageDetail(
            id=build_snapshot_message_id(message_id=message_id, message_index=message_index),
            activity_type='request_instruction',
            content=AIChatRequestInstructionActivityContentSchemaBase(
                text=serialize_instruction_activity_text(first_part),
                conversation_id=conversation_id,
                persisted_message_id=message_id,
                provider_id=provider_id,
                model_id=model_id,
                created_time=part_created_time,
                message_index=message_index,
                message_type='normal',
            ),
            **message_meta,
        )
    return None


def serialize_response_message(
    *,
    message: ModelResponse,
    conversation_id: str | None,
    message_id: int | None,
    provider_id: int | None,
    model_id: str | None,
    message_index: int,
) -> list[SnapshotMessage]:
    """
    序列化响应消息

    :param message: 响应消息
    :param conversation_id: 对话 ID
    :param message_id: 持久化消息 ID
    :param provider_id: 供应商 ID
    :param model_id: 模型 ID
    :param message_index: 消息索引
    :return:
    """
    response_snapshot_messages: list[SnapshotMessage] = []
    base_meta: dict[str, SnapshotMetaValue] = {
        'conversation_id': conversation_id,
        'persisted_message_id': message_id,
        'provider_id': provider_id,
        'model_id': model_id or message.model_name,
        'created_time': message.timestamp,
        'message_index': message_index,
        'message_type': 'error' if (message.metadata or {}).get('is_error') else 'normal',
    }
    assistant_text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for part_index, part in enumerate(message.parts):
        if isinstance(part, ThinkingPart):
            response_snapshot_messages.append(
                AIChatReasoningMessageDetail(
                    id=build_snapshot_message_id(
                        message_id=message_id,
                        message_index=message_index,
                        suffix=f'_reasoning_{part_index}',
                    ),
                    content=part.content,
                    **base_meta,
                )
            )
            continue
        if isinstance(part, TextPart):
            assistant_text_parts.append(part.content)
            continue
        if isinstance(part, FilePart):
            response_snapshot_messages.append(
                AIChatActivityMessageDetail(
                    id=build_snapshot_message_id(
                        message_id=message_id,
                        message_index=message_index,
                        suffix=f'_file_{part_index}',
                    ),
                    activity_type='assistant_file',
                    content=AIChatAssistantFileActivityContentSchemaBase(
                        file=build_input_content(part.content),
                        conversation_id=conversation_id,
                        persisted_message_id=message_id,
                        provider_id=provider_id,
                        model_id=model_id or message.model_name,
                        created_time=message.timestamp,
                        message_index=message_index,
                        message_type='error' if (message.metadata or {}).get('is_error') else 'normal',
                    ),
                    **base_meta,
                )
            )
            continue
        if isinstance(part, ToolCallPart):
            tool_calls.append(
                ToolCall(
                    id=part.tool_call_id,
                    function=FunctionCall(
                        name=part.tool_name,
                        arguments=(
                            part.args if isinstance(part.args, str) else json.dumps(part.args or {}, ensure_ascii=False)
                        ),
                    ),
                )
            )
            continue
        if isinstance(part, ToolReturnPart):
            content = serialize_tool_return_content(part.content)
            response_snapshot_messages.append(
                AIChatToolMessageDetail(
                    id=build_snapshot_message_id(
                        message_id=message_id,
                        message_index=message_index,
                        suffix=f'_tool_{part_index}',
                    ),
                    content=content,
                    tool_call_id=part.tool_call_id,
                    error=None if part.outcome == 'success' else content,
                    **base_meta,
                )
            )
    if assistant_text_parts or tool_calls or not response_snapshot_messages:
        response_snapshot_messages.insert(
            0,
            AIChatAssistantMessageDetail(
                id=build_snapshot_message_id(message_id=message_id, message_index=message_index),
                content=''.join(assistant_text_parts) or None,
                tool_calls=tool_calls or None,
                **base_meta,
            ),
        )
    return response_snapshot_messages


def serialize_messages_to_snapshot(
    messages: Sequence[ModelMessage],
    *,
    conversation_id: str | None = None,
    message_ids: Sequence[int | None] | None = None,
    provider_ids: Sequence[int | None] | None = None,
    model_ids: Sequence[str | None] | None = None,
) -> AIChatMessagesSnapshotDetail:
    """
    序列化模型消息为快照

    :param messages: 模型消息列表
    :param conversation_id: 对话 ID
    :param message_ids: 持久化消息 ID 列表
    :param provider_ids: 供应商 ID 列表
    :param model_ids: 模型 ID 列表
    :return:
    """
    snapshot_messages: list[AIChatSnapshotMessageDetail] = []
    for model_message_index, message in enumerate(messages):
        message_id = message_ids[model_message_index] if message_ids else None
        provider_id = provider_ids[model_message_index] if provider_ids else None
        model_id = model_ids[model_message_index] if model_ids else None
        message_index = len(snapshot_messages)
        if isinstance(message, ModelRequest):
            snapshot_message = serialize_request_message(
                message=message,
                conversation_id=conversation_id,
                message_id=message_id,
                provider_id=provider_id,
                model_id=model_id,
                message_index=message_index,
            )
            if snapshot_message is not None:
                snapshot_messages.append(snapshot_message)
            continue
        if isinstance(message, ModelResponse):
            snapshot_messages.extend(
                serialize_response_message(
                    message=message,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    provider_id=provider_id,
                    model_id=model_id,
                    message_index=message_index,
                )
            )

    return AIChatMessagesSnapshotDetail(messages=snapshot_messages)
