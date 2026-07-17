from typing import ClassVar

from backend.plugin.ai.chat.generation.base import GenerationHandler
from backend.plugin.ai.enums import AIChatGenerationType


class TextGenerationHandler(GenerationHandler):
    """文本生成模式处理器"""

    generation_type: ClassVar[AIChatGenerationType] = AIChatGenerationType.text

    def get_output_type(self) -> type[str]:
        """
        获取文本生成输出类型

        :return:
        """
        return str
