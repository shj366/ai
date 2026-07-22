from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.ai.crud.crud_mcp import ai_mcp_dao
from backend.plugin.ai.enums import McpType
from backend.plugin.ai.model import AIMcp
from backend.plugin.ai.schema.mcp import CreateAIMcpParam, UpdateAIMcpParam
from backend.utils.pattern_validate import match_string


class AIMcpService:
    """AI MCP 服务类"""

    @staticmethod
    def _normalize_transport_fields(obj: CreateAIMcpParam | UpdateAIMcpParam) -> CreateAIMcpParam | UpdateAIMcpParam:
        """
        规范化 MCP 传输相关字段

        :param obj: 创建或更新 MCP 参数
        :return:
        """
        command = (obj.command or '').strip()
        url = str(obj.url).strip() if obj.url else None

        if obj.type == McpType.stdio:
            if not command:
                raise errors.RequestError(msg='stdio 类型 MCP 必须填写启动命令')
            return obj.model_copy(update={'command': command, 'url': None, 'headers': None})

        if obj.type in (McpType.sse, McpType.streamable_http):
            if not url:
                raise errors.RequestError(msg='sse/streamable_http 类型 MCP 必须填写 URL')
            return obj.model_copy(update={'command': '', 'args': None, 'env': None, 'url': url})

        raise errors.RequestError(msg='不支持的 MCP 类型')

    @staticmethod
    async def get_all(*, db: AsyncSession) -> Sequence[AIMcp]:
        """
        获取所有 MCP

        :param db: 数据库会话
        :return:
        """
        return await ai_mcp_dao.get_all(db)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> AIMcp:
        """
        获取 MCP

        :param db: 数据库会话
        :param pk: MCP ID
        :return:
        """
        mcp = await ai_mcp_dao.get(db, pk)
        if not mcp:
            raise errors.NotFoundError(msg='MCP 不存在')
        return mcp

    @staticmethod
    async def get_by_ids(*, db: AsyncSession, mcp_ids: list[int]) -> Sequence[AIMcp]:
        """
        通过 ID 列表获取 MCP

        :param db: 数据库会话
        :param mcp_ids: MCP ID 列表
        :return:
        """
        return await ai_mcp_dao.get_by_ids(db, mcp_ids)

    @staticmethod
    async def get_list(*, db: AsyncSession, name: str | None, type: int | None) -> dict[str, Any]:
        """
        获取 MCP 列表

        :param db: 数据库会话
        :param name: MCP 名称
        :param type: MCP 类型
        :return:
        """
        mcp_select = await ai_mcp_dao.get_select(name=name, type=type)
        return await paging_data(db, mcp_select)

    async def create(self, *, db: AsyncSession, obj: CreateAIMcpParam) -> None:
        """
        创建 MCP

        :param db: 数据库会话
        :param obj: 创建 MCP 参数
        :return:
        """
        obj = self._normalize_transport_fields(obj)
        if obj.tool_prefix and not match_string(r'^[A-Za-z0-9_-]+$', obj.tool_prefix):
            raise errors.RequestError(msg='MCP 工具名称前缀仅支持字母、数字、下划线和连字符')
        mcp = await ai_mcp_dao.get_by_name(db, name=obj.name)
        if mcp:
            raise errors.ConflictError(msg='MCP 已存在')
        await ai_mcp_dao.create(db, obj)

    async def update(self, *, db: AsyncSession, pk: int, obj: UpdateAIMcpParam) -> int:
        """
        更新 MCP

        :param db: 数据库会话
        :param pk: MCP ID
        :param obj: 更新 MCP 参数
        :return:
        """
        obj = self._normalize_transport_fields(obj)
        if obj.tool_prefix and not match_string(r'^[A-Za-z0-9_-]+$', obj.tool_prefix):
            raise errors.RequestError(msg='MCP 工具名称前缀仅支持字母、数字、下划线和连字符')
        mcp = await ai_mcp_dao.get(db, pk)
        if not mcp:
            raise errors.NotFoundError(msg='MCP 不存在')
        if mcp.name != obj.name and await ai_mcp_dao.get_by_name(db, name=obj.name):
            raise errors.ConflictError(msg='MCP 已存在')
        return await ai_mcp_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除 MCP

        :param db: 数据库会话
        :param pk: MCP ID
        :return:
        """
        return await ai_mcp_dao.delete(db, pk)


ai_mcp_service: AIMcpService = AIMcpService()
