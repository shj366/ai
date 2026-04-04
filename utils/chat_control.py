from typing import Any

from pydantic_ai import ModelSettings
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.models.google import GoogleModelSettings
from pydantic_ai.models.openai import OpenAIChatModelSettings, OpenAIResponsesModelSettings
from pydantic_ai.models.openrouter import OpenRouterModelSettings
from pydantic_ai.models.xai import XaiModelSettings

from backend.plugin.ai.enums import AIChatGenerationType, AIProviderType, AIWebSearchType
from backend.plugin.ai.schema.chat import AIChatForwardedPropsParam


def _collect_model_settings(*, chat_metadata: AIChatForwardedPropsParam, fields: tuple[str, ...]) -> dict[str, Any]:
    """
    收集请求中显式传入且值非 ``None`` 的模型参数

    :param chat_metadata: 聊天元数据
    :param fields: 支持的字段列表
    :return:
    """
    return chat_metadata.model_dump(include=set(fields), exclude_unset=True, exclude_none=True)


def build_model_settings(*, chat_metadata: AIChatForwardedPropsParam, provider_type: int) -> ModelSettings | Any:
    """
    按供应商构建模型配置

    :param chat_metadata: 聊天元数据
    :param provider_type: 供应商类型
    :return:
    """

    provider = AIProviderType(provider_type)
    common_model_setting_fields = (
        'max_tokens',
        'temperature',
        'top_p',
        'timeout',
        'parallel_tool_calls',
        'seed',
        'presence_penalty',
        'frequency_penalty',
        'logit_bias',
        'stop_sequences',
        'extra_headers',
        'extra_body',
    )
    model_setting_fields = common_model_setting_fields
    if provider == AIProviderType.anthropic:
        model_setting_fields = tuple(
            field
            for field in common_model_setting_fields
            if field not in {'seed', 'presence_penalty', 'frequency_penalty', 'logit_bias'}
        )
    elif provider == AIProviderType.google:
        model_setting_fields = tuple(
            field
            for field in common_model_setting_fields
            if field not in {'parallel_tool_calls', 'logit_bias', 'extra_body'}
        )
    elif provider == AIProviderType.xai:
        model_setting_fields = tuple(
            field
            for field in common_model_setting_fields
            if field not in {'timeout', 'seed', 'logit_bias', 'extra_headers', 'extra_body'}
        )

    if provider == AIProviderType.openai:
        return OpenAIChatModelSettings(
            **_collect_model_settings(chat_metadata=chat_metadata, fields=common_model_setting_fields),
        )

    if provider == AIProviderType.openai_responses:
        settings = _collect_model_settings(chat_metadata=chat_metadata, fields=common_model_setting_fields)
        if chat_metadata.generation_type == AIChatGenerationType.text and chat_metadata.enable_builtin_tools:
            settings['openai_include_code_execution_outputs'] = True
        if chat_metadata.web_search == AIWebSearchType.builtin:
            settings['openai_include_web_search_sources'] = True
        return OpenAIResponsesModelSettings(**settings)

    if provider == AIProviderType.anthropic:
        return AnthropicModelSettings(
            **_collect_model_settings(chat_metadata=chat_metadata, fields=model_setting_fields),
        )

    if provider == AIProviderType.google:
        return GoogleModelSettings(
            **_collect_model_settings(chat_metadata=chat_metadata, fields=model_setting_fields),
        )

    if provider == AIProviderType.xai:
        return XaiModelSettings(**_collect_model_settings(chat_metadata=chat_metadata, fields=model_setting_fields))

    if provider == AIProviderType.openrouter:
        return OpenRouterModelSettings(
            **_collect_model_settings(chat_metadata=chat_metadata, fields=common_model_setting_fields),
        )

    return ModelSettings(**_collect_model_settings(chat_metadata=chat_metadata, fields=common_model_setting_fields))
