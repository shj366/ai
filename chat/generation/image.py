from typing import Any, ClassVar

from pydantic_ai import BinaryImage

from backend.common.exception import errors
from backend.plugin.ai.chat.generation.base import GenerationHandler
from backend.plugin.ai.enums import AIChatGenerationType, AIProviderType


class ImageGenerationHandler(GenerationHandler):
    """图片生成模式处理器"""

    generation_type: ClassVar[AIChatGenerationType] = AIChatGenerationType.image

    def validate_provider_type(self, provider_type: int | AIProviderType) -> None:
        """
        校验图片生成供应商

        :param provider_type: 供应商类型
        :return:
        """
        if AIProviderType(provider_type) not in {AIProviderType.google, AIProviderType.openai_responses}:
            raise errors.RequestError(msg='当前图片生成仅支持 Google 或 OpenAI Responses 供应商')

    def get_output_type(self) -> Any:
        """
        获取图片生成输出类型

        :return:
        """
        return [BinaryImage, str]
