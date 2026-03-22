from openai import AsyncOpenAI
from pydantic_ai import ModelSettings
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.models.xai import XaiModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.providers.xai import XaiProvider

from backend.common.exception import errors
from backend.plugin.ai.enums import AIProviderType

PydanticAIModel = OpenAIChatModel | AnthropicModel | GoogleModel | XaiModel | OpenRouterModel


def get_pydantic_model(
    provider_type: int, model_name: str, api_key: str, base_url: str, model_settings: ModelSettings
) -> PydanticAIModel:
    """
    获取 pydantic 模型

    :param provider_type: 供应商类型
    :param model_name: 模型名称
    :param api_key: 密钥
    :param base_url: API 基础域名
    :param model_settings: 模型配置
    :return:
    """
    match provider_type:
        case AIProviderType.openai:
            return OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(base_url=base_url, api_key=api_key),
                settings=model_settings,
            )
        case AIProviderType.anthropic:
            return AnthropicModel(
                model_name,
                provider=AnthropicProvider(base_url=base_url, api_key=api_key),
                settings=model_settings,
            )
        case AIProviderType.google:
            return GoogleModel(
                model_name,
                provider=GoogleProvider(base_url=base_url, api_key=api_key),
                settings=model_settings,
            )
        case AIProviderType.xai:
            return XaiModel(model_name, provider=XaiProvider(api_key=api_key), settings=model_settings)
        case AIProviderType.openrouter:
            openai_client = AsyncOpenAI(base_url=base_url, api_key=api_key) if base_url else None
            return OpenRouterModel(
                model_name,
                provider=OpenRouterProvider(api_key=api_key, openai_client=openai_client),
                settings=model_settings,
            )
        case _:
            raise errors.NotFoundError(msg=f'当前不支持此供应商: {provider_type}')
