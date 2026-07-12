from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.ai.schema.default_model import GetAIDefaultModelDetail
from backend.plugin.ai.schema.model import GetAIModelDetail
from backend.plugin.ai.schema.provider import GetAIProviderDetail


class GetAIProviderModelOptionDetail(GetAIProviderDetail):
    """AI 供应商模型选项详情"""

    models: list[GetAIModelDetail] = Field(description='启用的模型列表')


class GetAIModelOptionsDetail(SchemaBase):
    """AI 模型选项详情"""

    providers: list[GetAIProviderModelOptionDetail] = Field(description='启用的供应商及模型列表')
    default_model: GetAIDefaultModelDetail = Field(description='默认助手模型配置')
