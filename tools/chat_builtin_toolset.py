from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.toolsets import FunctionToolset

from backend.plugin.ai.dataclasses import ChatAgentDeps
from backend.utils.timezone import timezone


def build_chat_builtin_capability() -> AbstractCapability[ChatAgentDeps]:
    """构建聊天内置工具能力"""
    toolset: FunctionToolset[ChatAgentDeps] = FunctionToolset[ChatAgentDeps]()

    @toolset.tool_plain(defer_loading=True)
    def get_current_time() -> str:
        """获取当前时间"""
        return timezone.to_str(timezone.now())

    return Toolset(toolset)
