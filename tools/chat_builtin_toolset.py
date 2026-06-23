import json
from datetime import date, datetime

from pydantic_ai.capabilities import AbstractCapability, Toolset
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from sqlalchemy import inspect, text

from backend.database.db import async_db_session
from backend.plugin.ai.dataclasses import ChatAgentDeps


def build_chat_builtin_capability() -> AbstractCapability[ChatAgentDeps]:
    """
    构建聊天内置工具能力

    :return:
    """
    toolset = FunctionToolset[ChatAgentDeps]()

    @toolset.tool_plain
    def get_current_time() -> str:
        """
        获取当前时间

        :return:
        """
        from backend.utils.timezone import timezone

        return timezone.to_str(timezone.now())

    @toolset.tool
    async def list_provider_models(ctx: RunContext[ChatAgentDeps], provider_id: int) -> list[dict[str, int | str]]:
        """
        获取指定供应商的可用模型列表

        :param ctx: 运行上下文
        :param provider_id: 供应商 ID
        :return:
        """
        _ = ctx
        from backend.plugin.ai.crud.crud_model import ai_model_dao

        async with async_db_session() as db:
            models = await ai_model_dao.get_all(db, provider_id=provider_id)
        return [
            {
                'id': item.id,
                'model_id': item.model_id,
                'provider_id': item.provider_id,
                'status': item.status,
            }
            for item in models
        ]

    @toolset.tool
    async def list_my_quick_phrases(ctx: RunContext[ChatAgentDeps]) -> list[dict[str, int | str]]:
        """
        获取当前用户快捷短语列表

        :param ctx: 运行上下文
        :return:
        """
        from backend.plugin.ai.service.quick_phrase_service import ai_quick_phrase_service

        async with async_db_session() as db:
            phrases = await ai_quick_phrase_service.get_all(db=db, user_id=ctx.deps.user_id)
        return [{'id': item.id, 'title': item.title, 'content': item.content} for item in phrases]

    @toolset.tool
    async def get_database_schema(ctx: RunContext[ChatAgentDeps], table_names: list[str] | None = None) -> str:
        """
        获取数据库表结构

        :param ctx: 运行上下文
        :param table_names: 指定表名列表，为空时返回可用表
        :return:
        """
        _ = ctx

        async with async_db_session() as db:
            conn = await db.connection()

            def inspect_schema(sync_connection):
                inspector = inspect(sync_connection)
                available_tables = inspector.get_table_names()

                if not table_names:
                    return {'available_tables': available_tables}

                schema: dict[str, list[dict[str, str | bool | None]]] = {}
                for table_name in table_names:
                    if table_name not in available_tables:
                        continue
                    columns = inspector.get_columns(table_name)
                    schema[table_name] = [
                        {
                            'name': column['name'],
                            'type': str(column['type']),
                            'nullable': column.get('nullable'),
                            'default': str(column.get('default')) if column.get('default') is not None else None,
                        }
                        for column in columns
                    ]
                return schema

            result = await conn.run_sync(inspect_schema)

        return json.dumps(result, ensure_ascii=False)

    @toolset.tool
    async def execute_sql_query(ctx: RunContext[ChatAgentDeps], sql: str) -> str:
        """
        执行只读 SQL 查询

        :param ctx: 运行上下文
        :param sql: SQL 语句
        :return:
        """
        _ = ctx
        sql_text = sql.strip()
        if not sql_text.upper().startswith('SELECT'):
            return json.dumps({'error': 'Only SELECT queries are allowed'}, ensure_ascii=False)

        async with async_db_session() as db:
            result = await db.execute(text(sql_text))
            rows = result.mappings().fetchmany(2000)

        def serialize_value(value):
            if isinstance(value, datetime | date):
                return value.isoformat()
            return value

        data = [{key: serialize_value(value) for key, value in row.items()} for row in rows]
        return json.dumps({'rows': data, 'row_count': len(data)}, ensure_ascii=False)

    @toolset.tool
    async def download_attachments(
        ctx: RunContext[ChatAgentDeps],
        entity_type: str,
        entity_ids: list[int],
    ) -> str:
        """
        准备下载指定业务实体的附件

        :param ctx: 运行上下文
        :param entity_type: 业务实体类型
        :param entity_ids: 业务实体 ID 列表
        :return:
        """
        _ = ctx
        normalized_ids = [int(item) for item in entity_ids if int(item) > 0]
        return json.dumps(
            {
                'action': 'download_attachments',
                'entity_type': entity_type,
                'entity_ids': normalized_ids,
                'message': f'prepared to download {len(normalized_ids)} item attachments',
            },
            ensure_ascii=False,
        )

    return Toolset(toolset)
