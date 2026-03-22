from backend.common.enums import IntEnum


class AIProviderType(IntEnum):
    """AI 供应商类型"""

    openai = 0
    anthropic = 1
    google = 2
    xai = 3
    openrouter = 4


class McpType(IntEnum):
    """Mcp 类型"""

    stdio = 0
    sse = 1
    streamable_http = 2
