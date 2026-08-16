from pydantic_ai.capabilities import NativeTool
from pydantic_ai.native_tools import CodeExecutionTool

from backend.common.exception import errors
from backend.plugin.ai.dataclasses import CapabilityContext, CapabilityResult
from backend.plugin.ai.enums import AIChatGenerationType


async def build_code_execution_capability(ctx: CapabilityContext) -> CapabilityResult:  # ruff:ignore[unused-async]
    """
    构建代码执行能力

    :param ctx: 能力构建上下文
    :return:
    """
    if not ctx.forwarded_props.enable_code_execution:
        return CapabilityResult(capability=None)
    if ctx.forwarded_props.generation_type != AIChatGenerationType.text:
        raise errors.RequestError(msg='原生代码执行仅支持文本生成')
    if CodeExecutionTool not in ctx.supported_native_tools:
        raise errors.RequestError(msg='当前模型不支持原生代码执行')
    return CapabilityResult(
        capability=NativeTool(CodeExecutionTool()),
        introduces_builtin_tool=True,
    )
