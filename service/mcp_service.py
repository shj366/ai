from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.ai.crud.crud_mcp import ai_mcp_dao
from backend.plugin.ai.enums import McpType
from backend.plugin.ai.model import AIMcp
from backend.plugin.ai.schema.mcp import CreateAIMcpParam, UpdateAIMcpParam
from backend.plugin.ai.utils.api_key_ops import restore_masked_sensitive_data
from backend.utils.pattern_validate import match_string


class AIMcpService:
    """AI MCP 服务类"""

    @staticmethod
    def _normalize_transport_fields(
        *,
        obj: CreateAIMcpParam | UpdateAIMcpParam,
    ) -> CreateAIMcpParam | UpdateAIMcpParam:
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
            return obj.model_copy(update={'command': None, 'args': None, 'env': None, 'url': url})

        raise errors.RequestError(msg='不支持的 MCP 类型')

    @staticmethod
    def _validate_transport_permission(*, type: McpType, is_superuser: bool) -> None:
        """
        校验 MCP 传输类型的执行权限

        :param type: MCP 类型
        :param is_superuser: 是否为超级管理员
        :return:
        """
        if type == McpType.stdio and not is_superuser:
            raise errors.AuthorizationError(msg='仅超级管理员可以使用 stdio MCP')

    @staticmethod
    async def get_all(*, db: AsyncSession, user_id: int) -> Sequence[AIMcp]:
        """
        获取所有 MCP

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await ai_mcp_dao.get_all(db, user_id)

    @staticmethod
    async def get(*, db: AsyncSession, pk: int, user_id: int) -> AIMcp:
        """
        获取 MCP

        :param db: 数据库会话
        :param pk: MCP ID
        :param user_id: 用户 ID
        :return:
        """
        mcp = await ai_mcp_dao.get(db, pk, user_id)
        if not mcp:
            raise errors.NotFoundError(msg='MCP 不存在')
        return mcp

    @staticmethod
    async def get_by_ids(
        *,
        db: AsyncSession,
        mcp_ids: list[int],
        user_id: int,
        is_superuser: bool,
    ) -> Sequence[AIMcp]:
        """
        通过 ID 列表获取 MCP

        :param db: 数据库会话
        :param mcp_ids: MCP ID 列表
        :param user_id: 用户 ID
        :param is_superuser: 是否为超级管理员
        :return:
        """
        unique_ids = list(dict.fromkeys(mcp_ids))
        if len(unique_ids) != len(mcp_ids):
            raise errors.RequestError(msg='MCP ID 列表中存在重复项')
        mcps = await ai_mcp_dao.get_by_ids(db, unique_ids, user_id)
        if len(mcps) != len(unique_ids):
            raise errors.NotFoundError(msg='MCP 不存在')
        for mcp in mcps:
            AIMcpService._validate_transport_permission(type=McpType(mcp.type), is_superuser=is_superuser)
        return mcps

    @staticmethod
    async def get_list(*, db: AsyncSession, user_id: int, name: str | None, type: int | None) -> dict[str, Any]:
        """
        获取 MCP 列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param name: MCP 名称
        :param type: MCP 类型
        :return:
        """
        mcp_select = await ai_mcp_dao.get_select(user_id=user_id, name=name, type=type)
        return await paging_data(db, mcp_select)

    async def create(
        self,
        *,
        db: AsyncSession,
        obj: CreateAIMcpParam,
        user_id: int,
        is_superuser: bool,
    ) -> None:
        """
        创建 MCP

        :param db: 数据库会话
        :param obj: 创建 MCP 参数
        :param user_id: 用户 ID
        :param is_superuser: 是否为超级管理员
        :return:
        """
        obj = self._normalize_transport_fields(obj=obj)
        self._validate_transport_permission(type=obj.type, is_superuser=is_superuser)
        if obj.tool_prefix and not match_string(r'^[A-Za-z0-9_-]+$', obj.tool_prefix):
            raise errors.RequestError(msg='MCP 工具名称前缀仅支持字母、数字、下划线和连字符')
        mcp = await ai_mcp_dao.get_by_name(db, name=obj.name, user_id=user_id)
        if mcp:
            raise errors.ConflictError(msg='MCP 已存在')
        await ai_mcp_dao.create(db, obj, user_id)

    async def update(
        self,
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateAIMcpParam,
        user_id: int,
        is_superuser: bool,
    ) -> int:
        """
        更新 MCP

        :param db: 数据库会话
        :param pk: MCP ID
        :param obj: 更新 MCP 参数
        :param user_id: 用户 ID
        :param is_superuser: 是否为超级管理员
        :return:
        """
        mcp = await ai_mcp_dao.get(db, pk, user_id)
        if not mcp:
            raise errors.NotFoundError(msg='MCP 不存在')
        obj = obj.model_copy(
            update={
                'headers': restore_masked_sensitive_data(obj.headers, mcp.headers),
                'env': restore_masked_sensitive_data(obj.env, mcp.env),
            }
        )
        obj = self._normalize_transport_fields(obj=obj)
        self._validate_transport_permission(type=obj.type, is_superuser=is_superuser)
        if obj.tool_prefix and not match_string(r'^[A-Za-z0-9_-]+$', obj.tool_prefix):
            raise errors.RequestError(msg='MCP 工具名称前缀仅支持字母、数字、下划线和连字符')
        if mcp.name != obj.name and await ai_mcp_dao.get_by_name(db, name=obj.name, user_id=user_id):
            raise errors.ConflictError(msg='MCP 已存在')
        return await ai_mcp_dao.update(db, pk, obj, user_id)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int, user_id: int) -> int:
        """
        删除 MCP

        :param db: 数据库会话
        :param pk: MCP ID
        :param user_id: 用户 ID
        :return:
        """
        return await ai_mcp_dao.delete(db, pk, user_id)


ai_mcp_service: AIMcpService = AIMcpService()
