from typing import Annotated, Any, TypeAlias

from ag_ui.core import (
    ActivityDeltaEvent,
    ActivityMessage,
    ActivitySnapshotEvent,
    AssistantMessage,
    AudioInputContent,
    BinaryInputContent,
    DeveloperMessage,
    DocumentInputContent,
    ImageInputContent,
    MessagesSnapshotEvent,
    ReasoningMessage,
    SystemMessage,
    TextInputContent,
    ToolMessage,
    UserMessage,
    VideoInputContent,
)
from pydantic import AliasChoices, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_ai.messages import UploadedFileProviderName

from backend.common.schema import SchemaBase
from backend.plugin.ai.protocol.chat import AIChatMessageMetaSchemaBase


class AIChatAgUiProtocolSchemaBase(SchemaBase):
    """AI Chat 协议模型基础配置（兼容 AG-UI 协议小驼峰）"""

    model_config = ConfigDict(alias_generator=to_camel)


class AIChatAgUiVendorMetadataSchemaBase(AIChatAgUiProtocolSchemaBase):
    """AI 对话供应商元信息"""

    model_config = ConfigDict(extra='forbid')

    filename: str | None = Field(default=None, description='文件名')


class AIChatAgUiInputContentMetadataSchemaBase(AIChatAgUiProtocolSchemaBase):
    """AI 对话输入内容元信息"""

    model_config = ConfigDict(extra='forbid')

    id: str | None = Field(default=None, description='附件 ID')
    filename: str | None = Field(default=None, description='文件名')
    vendor_metadata: AIChatAgUiVendorMetadataSchemaBase | None = Field(default=None, description='供应商扩展元数据')


class AIChatAgUiImageInputContentSchemaBase(ImageInputContent):
    """AI 对话图片输入内容"""

    metadata: AIChatAgUiInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatAgUiAudioInputContentSchemaBase(AudioInputContent):
    """AI 对话音频输入内容"""

    metadata: AIChatAgUiInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatAgUiVideoInputContentSchemaBase(VideoInputContent):
    """AI 对话视频输入内容"""

    metadata: AIChatAgUiInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatAgUiDocumentInputContentSchemaBase(DocumentInputContent):
    """AI 对话文档输入内容"""

    metadata: AIChatAgUiInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatAgUiBinaryInputContentSchemaBase(BinaryInputContent):
    """AI 对话二进制输入内容"""

    provider_name: UploadedFileProviderName | None = Field(default=None, description='供应商名称')
    identifier: str | None = Field(default=None, description='附件标识')
    vendor_metadata: AIChatAgUiVendorMetadataSchemaBase | None = Field(default=None, description='供应商扩展元数据')


AIChatAgUiInputContentParam: TypeAlias = Annotated[
    TextInputContent
    | AIChatAgUiImageInputContentSchemaBase
    | AIChatAgUiAudioInputContentSchemaBase
    | AIChatAgUiVideoInputContentSchemaBase
    | AIChatAgUiDocumentInputContentSchemaBase
    | AIChatAgUiBinaryInputContentSchemaBase,
    Field(discriminator='type'),
]


class AIChatAgUiRequestInstructionActivityContentSchemaBase(AIChatMessageMetaSchemaBase):
    """AI 对话请求指令活动内容"""

    text: str | list[dict[str, Any]] = Field(description='活动文本内容')


class AIChatAgUiAssistantFileActivityContentSchemaBase(AIChatMessageMetaSchemaBase):
    """AI 对话助手文件活动内容"""

    file: (
        AIChatAgUiImageInputContentSchemaBase
        | AIChatAgUiAudioInputContentSchemaBase
        | AIChatAgUiVideoInputContentSchemaBase
        | AIChatAgUiDocumentInputContentSchemaBase
        | AIChatAgUiBinaryInputContentSchemaBase
    ) = Field(description='文件内容')


class AIChatAgUiUserMessageParam(UserMessage, AIChatMessageMetaSchemaBase):
    """AI 对话用户消息参数"""

    content: str | list[AIChatAgUiInputContentParam]


class AIChatAgUiDeveloperMessageDetail(DeveloperMessage, AIChatMessageMetaSchemaBase):
    """AI 对话开发者消息详情"""


class AIChatAgUiAssistantMessageDetail(AssistantMessage, AIChatMessageMetaSchemaBase):
    """AI 对话助手消息详情"""


class AIChatAgUiSystemMessageDetail(SystemMessage, AIChatMessageMetaSchemaBase):
    """AI 对话系统消息详情"""


class AIChatAgUiToolMessageDetail(ToolMessage, AIChatMessageMetaSchemaBase):
    """AI 对话工具消息详情"""


class AIChatAgUiReasoningMessageDetail(ReasoningMessage, AIChatMessageMetaSchemaBase):
    """AI 对话推理消息详情"""


class AIChatAgUiActivityMessageDetail(ActivityMessage, AIChatMessageMetaSchemaBase):
    """AI 对话活动消息详情"""

    content: (
        AIChatAgUiRequestInstructionActivityContentSchemaBase | AIChatAgUiAssistantFileActivityContentSchemaBase
    ) = Field(description='活动消息内容')


AIChatAgUiSnapshotMessageDetail: TypeAlias = Annotated[
    AIChatAgUiDeveloperMessageDetail
    | AIChatAgUiUserMessageParam
    | AIChatAgUiAssistantMessageDetail
    | AIChatAgUiSystemMessageDetail
    | AIChatAgUiToolMessageDetail
    | AIChatAgUiActivityMessageDetail
    | AIChatAgUiReasoningMessageDetail,
    Field(discriminator='role'),
]


class AIChatAgUiMessagesSnapshotDetail(MessagesSnapshotEvent):
    """AI 对话消息快照详情"""

    messages: list[AIChatAgUiSnapshotMessageDetail] = Field(description='消息快照列表')


class AIChatAgUiActivityPatchOperationDetail(AIChatAgUiProtocolSchemaBase):
    """AI 对话活动补丁操作"""

    model_config = ConfigDict(extra='forbid')

    op: str = Field(description='补丁操作')
    path: str = Field(description='目标路径')
    from_: str | None = Field(
        default=None,
        alias='from',
        validation_alias=AliasChoices('from', 'from_'),
        serialization_alias='from',
        description='来源路径',
    )
    value: Any = Field(default=None, description='补丁值')


class AIChatAgUiActivitySnapshotEventDetail(ActivitySnapshotEvent):
    """AI 对话活动快照事件详情"""

    activity_type: str = Field(description='活动类型')
    content: (
        AIChatAgUiRequestInstructionActivityContentSchemaBase | AIChatAgUiAssistantFileActivityContentSchemaBase
    ) = Field(description='活动内容')


class AIChatAgUiActivityDeltaEventDetail(ActivityDeltaEvent):
    """AI 对话活动增量事件详情"""

    activity_type: str = Field(description='活动类型')
    patch: list[AIChatAgUiActivityPatchOperationDetail] = Field(description='活动补丁列表')
