from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.ai.policy.context import AIInvocationContext, AIInvocationResult


class AIResourcePolicy:
    """AI 资源与调用策略基类"""

    async def before_invoke(self, *, db: AsyncSession, context: AIInvocationContext) -> None:
        """
        AI 调用前策略校验

        同一调用周期内可使用 ``get_ai_policy_shared()`` 复用已查询数据，
        避免多个策略重复访问数据库。

        :param db: 数据库会话
        :param context: AI 调用策略上下文
        :return:
        """
        return

    async def after_invoke(
        self,
        *,
        db: AsyncSession,
        context: AIInvocationContext,
        result: AIInvocationResult,
    ) -> None:
        """
        AI 调用后策略通知

        同一调用周期内可使用 ``get_ai_policy_shared()`` 复用已查询数据，
        避免多个策略重复访问数据库。

        :param db: 数据库会话
        :param context: AI 调用策略上下文
        :param result: AI 调用结果策略上下文
        :return:
        """
        return
