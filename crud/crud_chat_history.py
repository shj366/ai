from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.ai.model import AIChatHistory
from backend.plugin.ai.schema.chat_history import CreateAIChatHistoryParam, UpdateAIChatHistoryParam


class CRUDAIChatHistory(CRUDPlus[AIChatHistory]):
    async def get(self, db: AsyncSession, pk: int) -> AIChatHistory | None:
        """
        获取聊天历史

        :param db: 数据库会话
        :param pk: 历史 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_conversation_id(self, db: AsyncSession, conversation_id: str) -> AIChatHistory | None:
        """
        通过会话 ID 获取聊天历史

        :param db: 数据库会话
        :param conversation_id: 会话 ID
        :return:
        """
        return await self.select_model_by_column(db, conversation_id=conversation_id)

    async def get_recent_list(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int,
        before: datetime | None = None,
    ) -> Sequence[AIChatHistory]:
        """
        获取最近聊天历史列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param limit: 返回数量
        :param before: 查询游标
        :return:
        """
        activity_time = func.coalesce(self.model.updated_time, self.model.created_time)
        stmt = select(self.model).where(self.model.user_id == user_id)
        if before is not None:
            stmt = stmt.where(activity_time < before)
        pinned_first = sa.case((self.model.pinned_time.is_(None), 1), else_=0)
        stmt = stmt.order_by(
            pinned_first, desc(activity_time), desc(self.model.pinned_time), desc(self.model.created_time)
        ).limit(limit + 1)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, obj: CreateAIChatHistoryParam) -> None:
        """
        创建聊天历史

        :param db: 数据库会话
        :param obj: 创建聊天历史参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateAIChatHistoryParam) -> int:
        """
        更新聊天历史

        :param db: 数据库会话
        :param pk: 历史 ID
        :param obj: 更新聊天历史参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete_by_conversation_id(self, db: AsyncSession, conversation_id: str, user_id: int) -> int:
        """
        通过会话 ID 删除聊天历史

        :param db: 数据库会话
        :param conversation_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        return await self.delete_model_by_column(db, conversation_id=conversation_id, user_id=user_id)


ai_chat_history_dao: CRUDAIChatHistory = CRUDAIChatHistory(AIChatHistory)
