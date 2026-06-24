from collections.abc import Sequence
from importlib import import_module
from typing import Any

from backend.plugin.ai.dataclasses import CapabilityContext, CapabilityResult

_EXTENSION_BUILDERS: tuple[str, ...] = (
    'backend.plugin.ai.tools.local_toolset:build_local_ai_toolset_capability',
)


async def build_extension_capabilities(ctx: CapabilityContext) -> Sequence[CapabilityResult]:
    """Build project-local AI capabilities without mixing them into upstream AI files."""
    results: list[CapabilityResult] = []
    for builder_path in _EXTENSION_BUILDERS:
        module_path, _, attr_name = builder_path.partition(':')
        if not module_path or not attr_name:
            continue
        try:
            module = import_module(module_path)
        except ModuleNotFoundError as e:
            if e.name == module_path:
                continue
            raise
        builder = getattr(module, attr_name)
        outcome = await builder(ctx)
        normalized: Sequence[Any] = outcome if isinstance(outcome, Sequence) else (outcome,)
        results.extend(normalized)
    return results
