import json
from datetime import date, datetime

from pydantic_ai.capabilities import Toolset
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from sqlalchemy import inspect, text

from backend.database.db import async_db_session
from backend.plugin.ai.capabilities.base import function_tools_allowed
from backend.plugin.ai.dataclasses import CapabilityContext, CapabilityResult, ChatAgentDeps


async def build_local_ai_toolset_capability(ctx: CapabilityContext) -> CapabilityResult:  # noqa: RUF029
    """Build project-local function tools for the AI plugin."""
    if not ctx.forwarded_props.enable_builtin_tools:
        return CapabilityResult(capability=None)
    if not function_tools_allowed(
        adapter=ctx.adapter,
        supports_tools=ctx.supports_tools,
        has_builtin_tools=ctx.has_builtin_tools,
    ):
        return CapabilityResult(capability=None)

    toolset = FunctionToolset[ChatAgentDeps]()

    @toolset.tool
    async def get_database_schema(ctx: RunContext[ChatAgentDeps], table_names: list[str] | None = None) -> str:
        """
        Get database table schemas.

        :param ctx: Run context
        :param table_names: Optional table names. Returns available tables when omitted.
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
        Execute a read-only SQL query.

        :param ctx: Run context
        :param sql: SQL statement
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
        Prepare downloading attachments for business entities.

        :param ctx: Run context
        :param entity_type: Business entity type
        :param entity_ids: Business entity IDs
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

    return CapabilityResult(
        capability=Toolset(toolset),
        introduces_function_tool_source=True,
    )
