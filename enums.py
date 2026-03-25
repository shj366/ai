from backend.common.enums import IntEnum, StrEnum


class AIProviderType(IntEnum):
    """AI 供应商类型"""

    openai = 0
    anthropic = 1
    google = 2
    xai = 3
    openrouter = 4

    @property
    def default_api_path(self) -> str:
        return {
            AIProviderType.openai: '/v1',
            AIProviderType.anthropic: '',
            AIProviderType.google: '/v1beta',
            AIProviderType.xai: '/v1',
            AIProviderType.openrouter: '/api/v1',
        }[self]


class McpType(IntEnum):
    """Mcp 类型"""

    stdio = 0
    sse = 1
    streamable_http = 2


class AIChatAttachmentType(StrEnum):
    """聊天附件类型"""

    image = 'image'
    audio = 'audio'
    video = 'video'
    document = 'document'


class AIChatAttachmentSourceType(StrEnum):
    """聊天附件来源类型"""

    url = 'url'
    base64 = 'base64'


class AIChatMessageRoleType(StrEnum):
    """聊天消息角色"""

    user = 'user'
    thinking = 'thinking'
    model = 'model'


class AIChatOutputModeType(StrEnum):
    """聊天输出模式"""

    text = 'text'
    tool = 'tool'
    native = 'native'
    prompted = 'prompted'
