from abc import ABC, abstractmethod
from typing import Any, ClassVar

from backend.plugin.ai.enums import AIChatGenerationType, AIProviderType


class GenerationHandler(ABC):
    """生成模式处理器"""

    generation_type: ClassVar[AIChatGenerationType]

    def validate_provider_type(self, provider_type: int | AIProviderType) -> None:
        """
        校验供应商是否支持当前生成模式

        :param provider_type: 供应商类型
        :return:
        """
        return

    @abstractmethod
    def get_output_type(self) -> Any:
        """
        获取 Agent 输出类型

        :return:
        """
