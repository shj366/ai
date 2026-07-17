from contextvars import ContextVar, Token
from typing import Any

# 同一 AI 调用周期内策略共享缓存，避免多个策略重复查库
_ai_policy_shared: ContextVar[dict[str, Any] | None] = ContextVar('ai_policy_shared', default=None)


def begin_ai_policy_shared() -> tuple[dict[str, Any], Token[dict[str, Any] | None]]:
    """
    开启策略共享缓存

    :return: 缓存字典与 context token
    """
    shared: dict[str, Any] = {}
    return shared, _ai_policy_shared.set(shared)


def end_ai_policy_shared(token: Token[dict[str, Any] | None]) -> None:
    """
    结束策略共享缓存

    :param token: begin 返回的 token
    :return:
    """
    _ai_policy_shared.reset(token)


def get_ai_policy_shared() -> dict[str, Any]:
    """
    获取当前调用周期的策略共享缓存

    策略实现可将查询结果写入该字典，供后续策略复用。未处于策略管线内时返回空字典。

    :return:
    """
    shared = _ai_policy_shared.get()
    return shared if shared is not None else {}
