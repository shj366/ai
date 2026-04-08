from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

from ag_ui.core import (
    ActivityDeltaEvent,
    ActivityMessage,
    ActivitySnapshotEvent,
    AssistantMessage,
    AudioInputContent,
    BinaryInputContent,
    CustomEvent,
    DeveloperMessage,
    DocumentInputContent,
    ImageInputContent,
    MessagesSnapshotEvent,
    RawEvent,
    ReasoningEncryptedValueEvent,
    ReasoningEndEvent,
    ReasoningMessage,
    ReasoningMessageChunkEvent,
    ReasoningMessageContentEvent,
    ReasoningMessageEndEvent,
    ReasoningMessageStartEvent,
    ReasoningStartEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateDeltaEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    SystemMessage,
    TextInputContent,
    TextMessageChunkEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
    ThinkingTextMessageContentEvent,
    ThinkingTextMessageEndEvent,
    ThinkingTextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallChunkEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
    ToolMessage,
    UserMessage,
    VideoInputContent,
)
from pydantic import AliasChoices, ConfigDict, Field, RootModel

from backend.common.schema import SchemaBase


class AIChatMessageMetaSchemaBase(SchemaBase):
    """AI 对话消息扩展元信息"""

    model_config = ConfigDict(extra='forbid')

    conversation_id: str | None = Field(default=None, description='对话 ID')
    persisted_message_id: int | None = Field(default=None, description='持久化消息 ID')
    provider_id: int | None = Field(default=None, description='供应商 ID')
    model_id: str | None = Field(default=None, description='模型 ID')
    message_type: Literal['normal', 'error'] | None = Field(default=None, description='消息类型')
    message_index: int | None = Field(default=None, description='消息索引')
    created_time: datetime | None = Field(default=None, description='创建时间')


class AIChatVendorMetadataSchemaBase(SchemaBase):
    """AI 对话供应商元信息"""

    model_config = ConfigDict(extra='forbid')

    filename: str | None = Field(default=None, description='文件名')


class AIChatInputContentMetadataSchemaBase(SchemaBase):
    """AI 对话输入内容元信息"""

    model_config = ConfigDict(extra='forbid')

    id: str | None = Field(default=None, description='附件 ID')
    filename: str | None = Field(default=None, description='文件名')
    vendor_metadata: AIChatVendorMetadataSchemaBase | None = Field(default=None, description='供应商扩展元数据')


class AIChatImageInputContentSchemaBase(ImageInputContent):
    """AI 对话图片输入内容"""

    metadata: AIChatInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatAudioInputContentSchemaBase(AudioInputContent):
    """AI 对话音频输入内容"""

    metadata: AIChatInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatVideoInputContentSchemaBase(VideoInputContent):
    """AI 对话视频输入内容"""

    metadata: AIChatInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatDocumentInputContentSchemaBase(DocumentInputContent):
    """AI 对话文档输入内容"""

    metadata: AIChatInputContentMetadataSchemaBase | None = Field(default=None, description='输入元信息')


class AIChatBinaryInputContentSchemaBase(BinaryInputContent):
    """AI 对话二进制输入内容"""

    provider_name: str | None = Field(default=None, description='供应商名称')
    identifier: str | None = Field(default=None, description='附件标识')
    vendor_metadata: AIChatVendorMetadataSchemaBase | None = Field(default=None, description='供应商扩展元数据')


AIChatInputContentParam: TypeAlias = Annotated[
    TextInputContent
    | AIChatImageInputContentSchemaBase
    | AIChatAudioInputContentSchemaBase
    | AIChatVideoInputContentSchemaBase
    | AIChatDocumentInputContentSchemaBase
    | AIChatBinaryInputContentSchemaBase,
    Field(discriminator='type'),
]


class AIChatRequestInstructionActivityContentSchemaBase(AIChatMessageMetaSchemaBase):
    """AI 对话请求指令活动内容"""

    text: str | list[dict[str, Any]] = Field(description='活动文本内容')


class AIChatAssistantFileActivityContentSchemaBase(AIChatMessageMetaSchemaBase):
    """AI 对话助手文件活动内容"""

    file: (
        AIChatImageInputContentSchemaBase
        | AIChatAudioInputContentSchemaBase
        | AIChatVideoInputContentSchemaBase
        | AIChatDocumentInputContentSchemaBase
        | AIChatBinaryInputContentSchemaBase
    ) = Field(description='文件内容')


class AIChatUserMessageParam(UserMessage, AIChatMessageMetaSchemaBase):
    """AI 对话用户消息参数"""

    content: str | list[AIChatInputContentParam]


class AIChatDeveloperMessageDetail(DeveloperMessage, AIChatMessageMetaSchemaBase):
    """AI 对话开发者消息详情"""


class AIChatAssistantMessageDetail(AssistantMessage, AIChatMessageMetaSchemaBase):
    """AI 对话助手消息详情"""


class AIChatSystemMessageDetail(SystemMessage, AIChatMessageMetaSchemaBase):
    """AI 对话系统消息详情"""


class AIChatToolMessageDetail(ToolMessage, AIChatMessageMetaSchemaBase):
    """AI 对话工具消息详情"""


class AIChatReasoningMessageDetail(ReasoningMessage, AIChatMessageMetaSchemaBase):
    """AI 对话推理消息详情"""


class AIChatActivityMessageDetail(ActivityMessage, AIChatMessageMetaSchemaBase):
    """AI 对话活动消息详情"""

    content: AIChatRequestInstructionActivityContentSchemaBase | AIChatAssistantFileActivityContentSchemaBase = Field(
        description='活动消息内容'
    )


AIChatSnapshotMessageDetail: TypeAlias = Annotated[
    AIChatDeveloperMessageDetail
    | AIChatUserMessageParam
    | AIChatAssistantMessageDetail
    | AIChatSystemMessageDetail
    | AIChatToolMessageDetail
    | AIChatActivityMessageDetail
    | AIChatReasoningMessageDetail,
    Field(discriminator='role'),
]


class AIChatMessagesSnapshotDetail(MessagesSnapshotEvent):
    """AI 对话消息快照详情"""

    messages: list[AIChatSnapshotMessageDetail] = Field(description='消息快照列表')


class AIChatActivityPatchOperationDetail(SchemaBase):
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


class AIChatActivitySnapshotEventDetail(ActivitySnapshotEvent):
    """AI 对话活动快照事件详情"""

    activity_type: str = Field(description='活动类型')
    content: AIChatRequestInstructionActivityContentSchemaBase | AIChatAssistantFileActivityContentSchemaBase = Field(
        description='活动内容'
    )


class AIChatActivityDeltaEventDetail(ActivityDeltaEvent):
    """AI 对话活动增量事件详情"""

    activity_type: str = Field(description='活动类型')
    patch: list[AIChatActivityPatchOperationDetail] = Field(description='活动补丁列表')


AIChatStreamEventDetailType: TypeAlias = (
    RunStartedEvent
    | RunFinishedEvent
    | RunErrorEvent
    | StepStartedEvent
    | StepFinishedEvent
    | StateSnapshotEvent
    | StateDeltaEvent
    | RawEvent
    | CustomEvent
    | TextMessageStartEvent
    | TextMessageContentEvent
    | TextMessageEndEvent
    | TextMessageChunkEvent
    | ThinkingStartEvent
    | ThinkingTextMessageStartEvent
    | ThinkingTextMessageContentEvent
    | ThinkingTextMessageEndEvent
    | ThinkingEndEvent
    | ReasoningStartEvent
    | ReasoningMessageStartEvent
    | ReasoningMessageContentEvent
    | ReasoningMessageEndEvent
    | ReasoningMessageChunkEvent
    | ReasoningEndEvent
    | ReasoningEncryptedValueEvent
    | ToolCallStartEvent
    | ToolCallArgsEvent
    | ToolCallEndEvent
    | ToolCallChunkEvent
    | ToolCallResultEvent
    | AIChatActivitySnapshotEventDetail
    | AIChatActivityDeltaEventDetail
    | AIChatMessagesSnapshotDetail
)


class AIChatStreamEventDetail(RootModel[AIChatStreamEventDetailType]):
    """AI 对话流式事件详情"""
