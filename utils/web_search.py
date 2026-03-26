from typing import Any

from pydantic_ai.builtin_tools import WebSearchTool
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.common_tools.tavily import tavily_search_tool

from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.ai.enums import AIProviderType, AIWebSearchType


def supports_builtin_web_search(provider_type: int) -> bool:
    """
    判断当前供应商是否支持模型内置网络搜索

    :param provider_type: 供应商类型
    :return:
    """

    return AIProviderType(provider_type).supports_builtin_web_search


def build_chat_search_tools(*, web_search: AIWebSearchType, provider_type: int) -> tuple[list[Any], list[Any]]:
    """
    构建聊天搜索工具。

    :param web_search: 网络搜索模式
    :param provider_type: 供应商类型
    :return:
    """

    tools: list[Any] = []
    builtin_tools: list[Any] = []

    if web_search == AIWebSearchType.builtin:
        if supports_builtin_web_search(provider_type):
            builtin_tools.append(WebSearchTool())
        return tools, builtin_tools

    if web_search == AIWebSearchType.tavily:
        if not settings.AI_TAVILY_API_KEY:
            raise errors.RequestError(msg='Tavily 搜索暂不可用，请联系系统管理员')
        tools.append(tavily_search_tool(api_key=settings.AI_TAVILY_API_KEY))
        return tools, builtin_tools

    if web_search == AIWebSearchType.duckduckgo:
        tools.append(duckduckgo_search_tool())
        return tools, builtin_tools

    raise errors.RequestError(msg='不支持的网络搜索模式')
