from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, HttpUrl, field_serializer

from backend.common.schema import SchemaBase
from backend.plugin.ai.enums import McpType
from backend.plugin.ai.utils.api_key_ops import mask_sensitive_data


class AIMcpSchemaBase(SchemaBase):
    """AI MCP 基础模型"""

    name: str = Field(description='MCP 名称')
    command: str | None = Field(None, description='MCP 命令')
    type: McpType = Field(McpType.stdio, description='MCP 类型')
    description: str | None = Field(None, description='MCP 描述')
    url: HttpUrl | None = Field(None, description='MCP 端点链接')
    headers: dict[str, Any] | None = Field(None, description='请求 MCP 端点时的请求头')
    args: list[str] | None = Field(None, description='MCP 命令参数')
    env: dict[str, Any] | None = Field(None, description='MCP 环境变量')
    timeout: float = Field(5, description='客户端初始化超时时间（秒）')
    read_timeout: float = Field(5 * 60, description='等待新消息的最长时间（秒）')
    tool_prefix: str | None = Field(None, max_length=64, description='MCP 工具名称前缀')
    include_instructions: bool = Field(False, description='是否注入 MCP 服务说明')

    @field_serializer('url')
    def serialize_url(self, url: HttpUrl | None) -> str | None:
        """序列化 MCP 端点链接"""
        return str(url) if url else None


class CreateAIMcpParam(AIMcpSchemaBase):
    """创建 AI MCP 参数"""


class UpdateAIMcpParam(AIMcpSchemaBase):
    """更新 AI MCP 参数"""


class GetAIMcpDetail(AIMcpSchemaBase):
    """AI MCP 详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='MCP ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')

    @field_serializer('headers', 'env')
    def serialize_sensitive_data(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        """脱敏序列化 MCP 敏感配置"""
        return mask_sensitive_data(value)
