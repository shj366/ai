from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.ai.enums import AIChatAttachmentSourceType, AIChatAttachmentType, AIMessageRoleType


class UpdateAIMessageParam(SchemaBase):
    """更新消息参数"""

    content: str = Field(description='消息内容')


class GetAIMessageAttachmentDetail(SchemaBase):
    """消息附件详情"""

    type: AIChatAttachmentType = Field(description='附件类型')
    source_type: AIChatAttachmentSourceType = Field(description='附件来源类型')
    mime_type: str = Field(description='附件内容类型')
    name: str | None = Field(default=None, description='附件名称')
    url: str = Field(description='附件地址')


class GetAIMessageDetail(SchemaBase):
    """AI 消息详情"""

    message_id: int | None = Field(default=None, description='消息 ID')
    conversation_id: str | None = Field(default=None, description='对话 ID')
    message_index: int = Field(description='展示消息索引')
    role: AIMessageRoleType = Field(description='消息角色')
    timestamp: str = Field(description='消息时间')
    content: str = Field(description='消息内容')
    attachments: list[GetAIMessageAttachmentDetail] = Field(default_factory=list, description='消息附件列表')
