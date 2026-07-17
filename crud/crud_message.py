from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.ai.enums import AIMessageStatus
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
        return await self.select_model(db, pk, deleted=0)

    async def get_all(self, db: AsyncSession, conversation_id: str) -> Sequence[AIMessage]:
        """
        获取对话全部消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        return await self.select_models_order(db, 'id', 'asc', conversation_id=conversation_id, deleted=0)

    async def get_all_by_message_index(self, db: AsyncSession, conversation_id: str) -> Sequence[AIMessage]:
        """
        按聊天上下文顺序获取对话全部消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        return await self.select_models_order(
            db,
            ['message_index', 'id'],
            ['asc', 'asc'],
            conversation_id=conversation_id,
            deleted=0,
        )

    async def get_select(self, conversation_id: str) -> Select:
        """
        获取对话消息查询表达式

        :param conversation_id: 对话 ID
        :return:
        """
        return await self.select_order('id', 'asc', conversation_id=conversation_id, deleted=0)

    async def get_next_message_index(self, db: AsyncSession, conversation_id: str) -> int:
        """
        获取下一条消息索引

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        # 单次聚合查询，避免先拉实体再取字段
        result = await db.execute(
            select(func.max(self.model.message_index)).where(
                self.model.conversation_id == conversation_id,
                self.model.deleted == 0,
            )
        )
        max_index = result.scalar_one_or_none()
        return (max_index if max_index is not None else -1) + 1

    async def has_pending(self, db: AsyncSession, conversation_id: str) -> bool:
        """
        检查对话是否存在待完成消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        message = await self.select_model_by_column(
            db,
            conversation_id=conversation_id,
            status=AIMessageStatus.pending,
            deleted=0,
        )
        return message is not None

    async def create(self, db: AsyncSession, obj: dict[str, Any]) -> AIMessage:
        """
        创建单条消息并返回 ORM 对象

        :param db: 数据库会话
        :param obj: 消息字段
        :return:
        """
        message = self.model(**obj)
        db.add(message)
        await db.flush()
        return message

    async def bulk_create(self, db: AsyncSession, objs: list[dict[str, Any]]) -> None:
        """
        批量创建消息

        :param db: 数据库会话
        :param objs: 消息列表
        :return:
        """
        now = timezone.now()
        payloads = [
            {
                **obj,
                'created_time': obj.get('created_time', now),
                'updated_time': obj.get('updated_time'),
            }
            for obj in objs
        ]
        await self.bulk_create_models(db, payloads)

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
        if offset == 0:
            return 0
        # 单条 UPDATE，避免先 SELECT 再逐行 bulk_update
        result = await db.execute(
            update(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.message_index >= start_message_index,
                self.model.deleted == 0,
            )
            .values(message_index=self.model.message_index + offset)
        )
        return result.rowcount or 0

    async def update(self, db: AsyncSession, pk: int, obj: dict[str, Any]) -> int:
        """
        更新消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param obj: 更新内容
        :return:
        """
        return await self.update_model_by_column(db, obj, id=pk, deleted=0)

    async def finalize_pending(self, db: AsyncSession, pk: int, obj: dict[str, Any]) -> int:
        """
        完成待生成消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :param obj: 更新字段
        :return:
        """
        return await self.update_model_by_column(
            db,
            obj,
            id=pk,
            status=AIMessageStatus.pending,
            deleted=0,
        )

    async def delete_pending(self, db: AsyncSession, pk: int) -> int:
        """
        删除待生成消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        return await self.delete_model_by_column(
            db,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            id=pk,
            status=AIMessageStatus.pending,
            deleted=0,
        )

    async def delete_message_index_range(
        self,
        db: AsyncSession,
        conversation_id: str,
        start_message_index: int,
        end_message_index: int,
    ) -> int:
        """
        按消息索引范围逻辑删除消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :param start_message_index: 起始消息索引
        :param end_message_index: 结束消息索引
        :return:
        """
        # 单条 UPDATE（deleted = id），避免先 SELECT 再逐行 bulk_update
        result = await db.execute(
            update(self.model)
            .where(
                self.model.conversation_id == conversation_id,
                self.model.message_index >= start_message_index,
                self.model.message_index <= end_message_index,
                self.model.deleted == 0,
            )
            .values(
                deleted=self.model.id,
                deleted_time=timezone.now(),
            )
        )
        return result.rowcount or 0

    async def delete_message(self, db: AsyncSession, pk: int) -> int:
        """
        删除指定消息

        :param db: 数据库会话
        :param pk: 消息 ID
        :return:
        """
        return await self.delete_model_by_column(
            db,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            id=pk,
            deleted=0,
        )

    async def delete(self, db: AsyncSession, conversation_id: str) -> int:
        """
        删除对话全部消息

        :param db: 数据库会话
        :param conversation_id: 对话 ID
        :return:
        """
        return await self.delete_model_by_column(
            db,
            allow_multiple=True,
            logical_deletion=True,
            deleted_flag_column='deleted',
            deleted_flag_value=self.model.id,
            deleted_at_column='deleted_time',
            deleted_at_factory=timezone.now(),
            conversation_id=conversation_id,
            deleted=0,
        )


ai_message_dao: CRUDAIMessage = CRUDAIMessage(AIMessage)
