from typing import TYPE_CHECKING, Any

from pydantic_ai import ModelSettings
from pydantic_ai.models.anthropic import AnthropicModelSettings
from pydantic_ai.models.google import GoogleModelSettings
from pydantic_ai.models.openai import OpenAIChatModelSettings
from pydantic_ai.models.openrouter import OpenRouterModelSettings, OpenRouterReasoning
from pydantic_ai.models.xai import XaiModelSettings

from backend.plugin.ai.enums import AIChatReasoningEffortType, AIProviderType
from backend.plugin.ai.schema.chat import AIChatForwardedPropsParam

if TYPE_CHECKING:
    from anthropic.types.beta import BetaThinkingConfigEnabledParam
    from google.genai.types import ThinkingConfigDict
    from openai.types.shared.reasoning_effort import ReasoningEffort


def _collect_model_settings(*, chat_metadata: AIChatForwardedPropsParam, fields: tuple[str, ...]) -> dict[str, Any]:
    """
    收集当前供应商支持且请求中显式传入的模型参数

    :param chat_metadata: 聊天元数据
    :param fields: 支持的字段列表
    :return:
    """

    requested_fields = chat_metadata.model_fields_set
    settings: dict[str, Any] = {}
    for field in fields:
        if field not in requested_fields:
            continue
        value = getattr(chat_metadata, field)
        if value is not None:
            settings[field] = value
    return settings


def _build_openai_model_settings(
    *, chat_metadata: AIChatForwardedPropsParam, settings: dict[str, Any]
) -> OpenAIChatModelSettings:
    """
    构建 OpenAI 模型配置

    :param chat_metadata: 聊天元数据
    :param settings: 模型配置
    :return:
    """

    openai_reasoning_effort_map: dict[AIChatReasoningEffortType, str] = {
        AIChatReasoningEffortType.none: 'none',
        AIChatReasoningEffortType.minimal: 'minimal',
        AIChatReasoningEffortType.low: 'low',
        AIChatReasoningEffortType.medium: 'medium',
        AIChatReasoningEffortType.high: 'high',
        AIChatReasoningEffortType.xhigh: 'xhigh',
    }
    openai_reasoning_effort: ReasoningEffort = openai_reasoning_effort_map.get(chat_metadata.reasoning_effort)
    openai_settings = dict(settings)
    if openai_reasoning_effort is not None:
        openai_settings['openai_reasoning_effort'] = openai_reasoning_effort

    return OpenAIChatModelSettings(**openai_settings)


def _build_anthropic_model_settings(
    *, chat_metadata: AIChatForwardedPropsParam, settings: dict[str, Any]
) -> AnthropicModelSettings:
    """
    构建 Anthropic 模型配置

    :param chat_metadata: 聊天元数据
    :param settings: 模型配置
    :return:
    """

    anthropic_thinking: BetaThinkingConfigEnabledParam | None = None
    if chat_metadata.include_thinking:
        anthropic_thinking: BetaThinkingConfigEnabledParam = {
            'type': 'enabled',
            'budget_tokens': 2048,
        }

    anthropic_settings = dict(settings)
    if anthropic_thinking is not None:
        anthropic_settings['anthropic_thinking'] = anthropic_thinking

    return AnthropicModelSettings(**anthropic_settings)


def _build_google_model_settings(
    *, chat_metadata: AIChatForwardedPropsParam, settings: dict[str, Any]
) -> GoogleModelSettings:
    """
    构建 Google 模型配置

    :param chat_metadata: 聊天元数据
    :param settings: 模型配置
    :return:
    """

    google_thinking_config: ThinkingConfigDict | None = None
    if chat_metadata.include_thinking:
        google_thinking_config: ThinkingConfigDict = {'include_thoughts': True}

    google_settings = dict(settings)
    if google_thinking_config is not None:
        google_settings['google_thinking_config'] = google_thinking_config

    return GoogleModelSettings(**google_settings)


def _build_xai_model_settings(*, settings: dict[str, Any]) -> XaiModelSettings:
    """
    构建 xAI 模型配置

    :param settings: 模型配置
    :return:
    """

    return XaiModelSettings(**settings)


def _build_openrouter_model_settings(
    *, chat_metadata: AIChatForwardedPropsParam, settings: dict[str, Any]
) -> OpenRouterModelSettings:
    """
    构建 OpenRouter 模型配置

    :param chat_metadata: 聊天元数据
    :param settings: 模型配置
    :return:
    """

    openrouter_reasoning: OpenRouterReasoning | None = None
    if chat_metadata.include_thinking or chat_metadata.reasoning_effort:
        openrouter_reasoning: OpenRouterReasoning = {
            'enabled': chat_metadata.include_thinking,
        }
        openrouter_reasoning_effort_map: dict[AIChatReasoningEffortType, str] = {
            AIChatReasoningEffortType.none: 'none',
            AIChatReasoningEffortType.minimal: 'minimal',
            AIChatReasoningEffortType.low: 'low',
            AIChatReasoningEffortType.medium: 'medium',
            AIChatReasoningEffortType.high: 'high',
            AIChatReasoningEffortType.xhigh: 'xhigh',
        }
        effort = openrouter_reasoning_effort_map.get(chat_metadata.reasoning_effort)
        if effort is not None:
            openrouter_reasoning['effort'] = effort

    openrouter_settings = dict(settings)
    if openrouter_reasoning is not None:
        openrouter_settings['openrouter_reasoning'] = openrouter_reasoning

    return OpenRouterModelSettings(**openrouter_settings)


def build_model_settings(*, chat_metadata: AIChatForwardedPropsParam, provider_type: int) -> ModelSettings | Any:
    """
    构建模型配置

    :param chat_metadata: 聊天元数据
    :param provider_type: 供应商类型
    :return:
    """

    provider = AIProviderType(provider_type)
    model_setting_fields = (
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
    anthropic_model_setting_fields = tuple(
        field
        for field in model_setting_fields
        if field not in {'seed', 'presence_penalty', 'frequency_penalty', 'logit_bias'}
    )
    google_model_setting_fields = tuple(
        field for field in model_setting_fields if field not in {'parallel_tool_calls', 'logit_bias', 'extra_body'}
    )
    xai_model_setting_fields = tuple(
        field for field in model_setting_fields if field not in {'seed', 'logit_bias', 'extra_body'}
    )

    if provider == AIProviderType.openai:
        return _build_openai_model_settings(
            chat_metadata=chat_metadata,
            settings=_collect_model_settings(chat_metadata=chat_metadata, fields=model_setting_fields),
        )
    if provider == AIProviderType.anthropic:
        return _build_anthropic_model_settings(
            chat_metadata=chat_metadata,
            settings=_collect_model_settings(chat_metadata=chat_metadata, fields=anthropic_model_setting_fields),
        )
    if provider == AIProviderType.google:
        return _build_google_model_settings(
            chat_metadata=chat_metadata,
            settings=_collect_model_settings(chat_metadata=chat_metadata, fields=google_model_setting_fields),
        )
    if provider == AIProviderType.xai:
        return _build_xai_model_settings(
            settings=_collect_model_settings(chat_metadata=chat_metadata, fields=xai_model_setting_fields)
        )
    if provider == AIProviderType.openrouter:
        return _build_openrouter_model_settings(
            chat_metadata=chat_metadata,
            settings=_collect_model_settings(chat_metadata=chat_metadata, fields=model_setting_fields),
        )

    return ModelSettings(**_collect_model_settings(chat_metadata=chat_metadata, fields=model_setting_fields))
