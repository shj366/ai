from typing import Any

from pydantic_ai import ModelSettings
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.models.google import GoogleModelSettings
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.models.openrouter import OpenRouterModelSettings
from pydantic_ai.models.xai import XaiModelSettings

from backend.plugin.ai.enums import AIProviderType
from backend.plugin.ai.schema.chat import AIChatParam


def build_model_settings(*, chat: AIChatParam, provider_type: int) -> ModelSettings | Any:
    """
    构建模型配置

    :param chat: 聊天参数
    :param provider_type: 供应商类型
    :return:
    """
    common_settings = {
        'max_tokens': chat.max_tokens,
        'temperature': chat.temperature,
        'top_p': chat.top_p,
        'timeout': chat.timeout,
        'parallel_tool_calls': chat.parallel_tool_calls,
        'seed': chat.seed,
        'presence_penalty': chat.presence_penalty,
        'frequency_penalty': chat.frequency_penalty,
        'logit_bias': chat.logit_bias,
        'stop_sequences': chat.stop_sequences,
        'extra_headers': chat.extra_headers,
        'extra_body': chat.extra_body,
    }

    provider = AIProviderType(provider_type)
    if provider == AIProviderType.openai:
        return OpenAIChatModelSettings(
            **{k: v for k, v in common_settings.items() if v is not None},
            openai_reasoning_effort=chat.reasoning_effort,
            openai_reasoning_summary=chat.reasoning_summary,
        )
    if provider == AIProviderType.anthropic:
        return AnthropicModelSettings(
            **{
                k: v
                for k, v in common_settings.items()
                if k not in {'seed', 'presence_penalty', 'frequency_penalty', 'logit_bias'} and v is not None
            },
            anthropic_thinking={
                'type': 'enabled',
                'budget_tokens': 2048,
            }
            if chat.include_thinking
            else None,
        )
    if provider == AIProviderType.google:
        return GoogleModelSettings(
            **{
                k: v
                for k, v in common_settings.items()
                if k not in {'parallel_tool_calls', 'logit_bias', 'extra_body'} and v is not None
            },
            google_thinking_config={'include_thoughts': chat.include_thinking} if chat.include_thinking else None,
        )
    if provider == AIProviderType.xai:
        return XaiModelSettings(
            **{
                k: v
                for k, v in common_settings.items()
                if k not in {'seed', 'logit_bias', 'extra_body'} and v is not None
            },
            xai_reasoning_effort=chat.reasoning_effort,
        )
    if provider == AIProviderType.openrouter:
        return OpenRouterModelSettings(
            **{k: v for k, v in common_settings.items() if v is not None},
            openrouter_reasoning={
                'enabled': chat.include_thinking,
                'effort': chat.reasoning_effort,
                'summary': chat.reasoning_summary,
            }
            if chat.include_thinking or chat.reasoning_effort or chat.reasoning_summary
            else None,
        )
    return ModelSettings(**{k: v for k, v in common_settings.items() if v is not None})
