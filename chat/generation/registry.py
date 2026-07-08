from backend.common.exception import errors
from backend.plugin.ai.chat.generation.base import GenerationHandler
from backend.plugin.ai.chat.generation.image import ImageGenerationHandler
from backend.plugin.ai.chat.generation.text import TextGenerationHandler
from backend.plugin.ai.enums import AIChatGenerationType

_GENERATION_HANDLERS: dict[AIChatGenerationType, GenerationHandler] = {
    AIChatGenerationType.text: TextGenerationHandler(),
    AIChatGenerationType.image: ImageGenerationHandler(),
}


def get_generation_handler(generation_type: AIChatGenerationType) -> GenerationHandler:
    """
    获取生成模式处理器

    :param generation_type: 生成模式
    :return:
    """
    handler = _GENERATION_HANDLERS.get(generation_type)
    if handler is None:
        raise errors.RequestError(msg='暂不支持的生成模式')
    return handler
