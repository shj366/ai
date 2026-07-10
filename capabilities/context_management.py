import warnings

from collections.abc import Sequence

from pydantic_ai_harness.experimental import HarnessExperimentalWarning

with warnings.catch_warnings():
    warnings.simplefilter('ignore', HarnessExperimentalWarning)
    from pydantic_ai_harness.experimental.compaction import ClampOversizedMessages, LimitWarner, SlidingWindow

from backend.core.conf import settings
from backend.plugin.ai.dataclasses import CapabilityContext, CapabilityResult
from backend.plugin.ai.enums import AIChatGenerationType


async def build_context_management_capabilities(  # noqa: RUF029
    ctx: CapabilityContext,
) -> Sequence[CapabilityResult]:
    """
    构建上下文管理能力

    :param ctx: 能力构建上下文
    :return:
    """
    if ctx.forwarded_props.generation_type != AIChatGenerationType.text:
        return ()

    results: list[CapabilityResult] = []
    if settings.AI_CONTEXT_CLAMP_OVERSIZED_ENABLED:
        results.append(
            CapabilityResult(
                capability=ClampOversizedMessages(max_part_chars=settings.AI_CONTEXT_MAX_PART_CHARS),
            )
        )
    if settings.AI_CONTEXT_SLIDING_WINDOW_ENABLED:
        results.append(
            CapabilityResult(
                capability=SlidingWindow(
                    max_messages=settings.AI_CONTEXT_MAX_MESSAGES,
                    keep_messages=settings.AI_CONTEXT_KEEP_MESSAGES,
                ),
            )
        )
    if settings.AI_CONTEXT_LIMIT_WARNING_ENABLED:
        results.append(
            CapabilityResult(
                capability=LimitWarner(
                    max_context_tokens=settings.AI_CONTEXT_MAX_TOKENS,
                    warning_threshold=settings.AI_CONTEXT_WARNING_THRESHOLD,
                ),
            )
        )
    return tuple(results)
