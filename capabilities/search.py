from collections.abc import Sequence

from pydantic_ai.capabilities import NativeTool, Toolset
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
from pydantic_ai.common_tools.exa import ExaToolset
from pydantic_ai.common_tools.tavily import tavily_search_tool
from pydantic_ai.native_tools import WebFetchTool, WebSearchTool
from pydantic_ai.toolsets import FunctionToolset

from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.ai.dataclasses import CapabilityContext, CapabilityResult
from backend.plugin.ai.enums import AIChatGenerationType, AIWebSearchType
from backend.plugin.ai.utils.dynamic_config import load_ai_config


def _build_web_fetch_capability(ctx: CapabilityContext) -> CapabilityResult | None:
    """
    构建原生网页抓取能力

    :param ctx: 能力构建上下文
    :return:
    """
    if not ctx.forwarded_props.enable_web_fetch:
        return None
    if ctx.forwarded_props.generation_type != AIChatGenerationType.text:
        raise errors.RequestError(msg='网页抓取仅支持文本生成')
    if WebFetchTool not in ctx.supported_native_tools:
        raise errors.RequestError(msg='当前模型不支持原生网页抓取')
    return CapabilityResult(capability=NativeTool(WebFetchTool()), introduces_builtin_tool=True)


async def build_search_capabilities(ctx: CapabilityContext) -> Sequence[CapabilityResult]:
    """
    构建联网搜索能力

    :param ctx: 能力构建上下文
    :return:
    """
    forwarded_props = ctx.forwarded_props
    web_search = forwarded_props.web_search

    results: list[CapabilityResult] = []

    match web_search:
        case AIWebSearchType.off:
            pass
        case AIWebSearchType.builtin:
            if WebSearchTool not in ctx.supported_native_tools:
                raise errors.RequestError(
                    msg='当前模型不支持内置联网搜索，请选择 Exa、Tavily、DuckDuckGo 或关闭联网搜索'
                )
            results.append(CapabilityResult(capability=NativeTool(WebSearchTool()), introduces_builtin_tool=True))
        case AIWebSearchType.exa:
            await load_ai_config(ctx.db)
            if not settings.AI_EXA_API_KEY:
                raise errors.RequestError(msg='未配置 AI_EXA_API_KEY，无法启用 Exa 搜索')
            results.append(
                CapabilityResult(
                    capability=Toolset(ExaToolset(api_key=settings.AI_EXA_API_KEY)),
                    introduces_function_tool_source=True,
                )
            )
        case AIWebSearchType.tavily:
            await load_ai_config(ctx.db)
            if not settings.AI_TAVILY_API_KEY:
                raise errors.RequestError(msg='未配置 AI_TAVILY_API_KEY，无法启用 Tavily 搜索')
            results.append(
                CapabilityResult(
                    capability=Toolset(FunctionToolset([tavily_search_tool(api_key=settings.AI_TAVILY_API_KEY)])),
                    introduces_function_tool_source=True,
                )
            )
        case AIWebSearchType.duckduckgo:
            results.append(
                CapabilityResult(
                    capability=Toolset(FunctionToolset([duckduckgo_search_tool()])),
                    introduces_function_tool_source=True,
                )
            )
        case _:
            raise errors.RequestError(msg='不支持的网络搜索模式')

    web_fetch = _build_web_fetch_capability(ctx)
    if web_fetch is not None:
        results.append(web_fetch)
    return tuple(results)
