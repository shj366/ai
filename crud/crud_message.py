from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.ai.model import AIMessage
from backend.utils.timezone import timezone


class CRUDAIMessage(CRUDPlus[AIMessage]):
    """AI 消息数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> AIMessage | None:
        """
        获取消息

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_all(self, db: AsyncSession, conversation_id: str) -> Sequence[AIMessage]:
        """
        获取对话全部消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        return await self.select_models_order(db, 'message_index', 'asc', conversation_id=conversation_id)

    async def get_select(self, conversation_id: str) -> Select:
        """
        获取对话消息查询表达式

        :param conversation_id: 对话 ID
        :return:
        """
        return await self.select_order('message_index', 'asc', conversation_id=conversation_id)

    async def bulk_create(self, db: AsyncSession, objs: list[dict[str, Any]]) -> None:
        """
        批量创建消息

        :param db: 数据库会话
        :param objs: 消息列表
        :return:
        """
        db.add_all([self.model(**obj) for obj in objs])
        await db.flush()

    async def update_message_indexes_offset(
        self,
        db: AsyncSession,
        conversation_id: str,
        start_message_index: int,
        offset: int,
    ) -> int:
        """
        平移指定索引及之后的消息索引

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :param start_message_index: 起始消息索引
        :param offset: 平移偏移量
        :return:
        """
        messages = await self.select_models_order(
            db,
            'message_index',
            'asc',
            conversation_id=conversation_id,
            message_index__ge=start_message_index,
        )

        if not messages:
            return 0

        return await self.bulk_update_models(
            db,
            [
                {
                    'id': message.id,
                    'message_index': message.message_index + offset,
                }
                for message in messages
            ],
        )

    async def update(self, db: AsyncSession, pk: int, obj: dict[str, Any]) -> int:
        """
        更新消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param obj: 更新内容
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete_message(self, db: AsyncSession, pk: int) -> int:
        """
        删除指定消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def delete_message_index_range(
        self,
        db: AsyncSession,
        conversation_id: str,
        start_message_index: int,
        end_message_index: int,
    ) -> int:
        """
        删除指定索引区间内的消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :param start_message_index: 起始消息索引
        :param end_message_index: 结束消息索引
        :return:
        """
        return await self.delete_model_by_column(
            db,
            allow_multiple=True,
            conversation_id=conversation_id,
            message_index__ge=start_message_index,
            message_index__le=end_message_index,
        )

    async def delete(self, db: AsyncSession, conversation_id: str) -> int:
        """
        删除对话全部消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, conversation_id=conversation_id)


ai_message_dao: CRUDAIMessage = CRUDAIMessage(AIMessage)
