from base64 import b64decode
from collections.abc import Sequence
from typing import Any, TypeAlias, cast

from ag_ui.core import InputContentDataSource, TextInputContent
from pydantic_ai import (
    AudioUrl,
    BinaryContent,
    DocumentUrl,
    ImageUrl,
    ModelRequest,
    UploadedFile,
    UserPromptPart,
    VideoUrl,
)

from backend.common.exception import errors
from backend.database.db import uuid4_str
from backend.plugin.ai.protocol.ag_ui.schema import (
    AIChatAgUiAudioInputContentSchemaBase,
    AIChatAgUiBinaryInputContentSchemaBase,
    AIChatAgUiDocumentInputContentSchemaBase,
    AIChatAgUiImageInputContentSchemaBase,
    AIChatAgUiUserMessageParam,
    AIChatAgUiVendorMetadataSchemaBase,
    AIChatAgUiVideoInputContentSchemaBase,
)

PromptContentItem: TypeAlias = str | AudioUrl | BinaryContent | DocumentUrl | ImageUrl | UploadedFile | VideoUrl
UserPromptContent: TypeAlias = str | Sequence[PromptContentItem]
MediaInputPart: TypeAlias = (
    AIChatAgUiImageInputContentSchemaBase
    | AIChatAgUiAudioInputContentSchemaBase
    | AIChatAgUiVideoInputContentSchemaBase
    | AIChatAgUiDocumentInputContentSchemaBase
)


def build_vendor_metadata_dict(
    *,
    vendor_metadata: AIChatAgUiVendorMetadataSchemaBase | None,
    filename: str | None = None,
) -> dict[str, Any] | None:
    """
    构建供应商元数据字典

    :param vendor_metadata: 供应商元数据模型
    :param filename: 文件名
    :return:
    """
    metadata: dict[str, Any] = {}
    if vendor_metadata and vendor_metadata.filename:
        metadata['filename'] = vendor_metadata.filename
    if filename:
        metadata['filename'] = filename
    return metadata or None


def build_binary_content(
    *,
    data: bytes,
    media_type: str,
    identifier: str | None,
    vendor_metadata: dict[str, Any] | None,
) -> BinaryContent:
    """
    构建二进制内容

    :param data: 二进制数据
    :param media_type: 媒体类型
    :param identifier: 标识
    :param vendor_metadata: 扩展元数据
    :return:
    """
    return BinaryContent.narrow_type(
        BinaryContent(
            data=data,
            media_type=media_type,
            identifier=identifier,
            vendor_metadata=vendor_metadata,
        )
    )


def build_file_url_content(
    *,
    url: str,
    media_type: str,
    identifier: str | None,
    vendor_metadata: dict[str, Any] | None,
) -> AudioUrl | DocumentUrl | ImageUrl | VideoUrl:
    """
    构建文件 URL 内容

    :param url: 文件地址
    :param media_type: 媒体类型
    :param identifier: 标识
    :param vendor_metadata: 扩展元数据
    :return:
    """
    constructor = {'image': ImageUrl, 'video': VideoUrl, 'audio': AudioUrl}.get(
        media_type.split('/', 1)[0], DocumentUrl
    )
    return constructor(
        url=url,
        media_type=media_type,
        identifier=identifier,
        vendor_metadata=vendor_metadata,
    )


def deserialize_binary_input_part(part: AIChatAgUiBinaryInputContentSchemaBase) -> PromptContentItem:
    """
    解析二进制输入片段

    :param part: 二进制输入片段
    :return:
    """
    vendor_metadata = build_vendor_metadata_dict(vendor_metadata=part.vendor_metadata, filename=part.filename)
    if part.id and part.provider_name:
        return UploadedFile(
            file_id=part.id,
            provider_name=part.provider_name,
            media_type=part.mime_type,
            identifier=part.identifier,
            vendor_metadata=vendor_metadata,
        )
    if part.url:
        try:
            parsed_binary = BinaryContent.from_data_uri(part.url)
        except ValueError:
            return build_file_url_content(
                url=part.url,
                media_type=part.mime_type,
                identifier=part.id,
                vendor_metadata=vendor_metadata,
            )
        return build_binary_content(
            data=parsed_binary.data,
            media_type=parsed_binary.media_type,
            identifier=part.id,
            vendor_metadata=vendor_metadata,
        )
    if part.data:
        return build_binary_content(
            data=b64decode(part.data),
            media_type=part.mime_type,
            identifier=part.id,
            vendor_metadata=vendor_metadata,
        )
    raise errors.RequestError(msg='聊天消息格式非法')


def deserialize_media_input_part(part: MediaInputPart) -> PromptContentItem:
    """
    解析媒体输入片段

    :param part: 媒体输入片段
    :return:
    """
    metadata = part.metadata
    mime_type = (
        part.source.mime_type
        or {
            AIChatAgUiImageInputContentSchemaBase: 'image/*',
            AIChatAgUiAudioInputContentSchemaBase: 'audio/*',
            AIChatAgUiVideoInputContentSchemaBase: 'video/*',
            AIChatAgUiDocumentInputContentSchemaBase: 'application/octet-stream',
        }[type(part)]
    )
    attachment_id = metadata.id if metadata and metadata.id else uuid4_str()
    vendor_metadata = build_vendor_metadata_dict(
        vendor_metadata=metadata.vendor_metadata if metadata else None,
        filename=metadata.filename if metadata else None,
    )
    if isinstance(part.source, InputContentDataSource):
        return build_binary_content(
            data=b64decode(part.source.value),
            media_type=mime_type,
            identifier=attachment_id,
            vendor_metadata=vendor_metadata,
        )
    try:
        parsed_binary = BinaryContent.from_data_uri(part.source.value)
    except ValueError:
        media_type = part.source.mime_type or mime_type
        return build_file_url_content(
            url=part.source.value,
            media_type=media_type,
            identifier=attachment_id,
            vendor_metadata=vendor_metadata,
        )
    return build_binary_content(
        data=parsed_binary.data,
        media_type=parsed_binary.media_type,
        identifier=attachment_id,
        vendor_metadata=vendor_metadata,
    )


def deserialize_current_user_message(message: AIChatAgUiUserMessageParam) -> ModelRequest:
    """
    解析当前轮用户消息，保留文件标识和文件名

    :param message: 用户消息
    :return:
    """
    content = message.content
    if isinstance(content, str):
        return ModelRequest(parts=[UserPromptPart(content=content)])

    user_prompt_content: list[PromptContentItem] = []
    for part in content:
        if isinstance(part, TextInputContent):
            user_prompt_content.append(part.text)
            continue
        if isinstance(part, AIChatAgUiBinaryInputContentSchemaBase):
            user_prompt_content.append(deserialize_binary_input_part(part))
            continue
        if isinstance(
            part,
            (
                AIChatAgUiImageInputContentSchemaBase,
                AIChatAgUiAudioInputContentSchemaBase,
                AIChatAgUiVideoInputContentSchemaBase,
                AIChatAgUiDocumentInputContentSchemaBase,
            ),
        ):
            user_prompt_content.append(deserialize_media_input_part(part))
            continue
        raise errors.RequestError(msg='聊天消息格式非法')

    if not user_prompt_content:
        raise errors.RequestError(msg='聊天消息不能为空')

    user_prompt: UserPromptContent
    if len(user_prompt_content) == 1 and isinstance(user_prompt_content[0], str):
        user_prompt = cast('str', user_prompt_content[0])
    else:
        user_prompt = user_prompt_content
    return ModelRequest(parts=[UserPromptPart(content=user_prompt)])
