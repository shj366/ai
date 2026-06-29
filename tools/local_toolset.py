import json
import re
import secrets
from datetime import date, datetime

import anyio
from pydantic_ai.capabilities import Toolset
from pydantic_ai.tools import RunContext
from pydantic_ai.toolsets import FunctionToolset
from sqlalchemy import inspect, select, text

from backend.core.path_conf import UPLOAD_DIR
from backend.database.db import async_db_session
from backend.plugin.ai.capabilities.base import function_tools_allowed
from backend.plugin.ai.dataclasses import CapabilityContext, CapabilityResult, ChatAgentDeps
from backend.plugin.attachment_export.core.attachment_download import attachment_download_service

HTML_PAGE_DIR = 'ai_pages'
MAX_HTML_PAGE_BYTES = 600_000


def _normalize_html_page_filename(title: str | None) -> str:
    stem = re.sub(r'[^A-Za-z0-9_-]+', '-', title or 'ai-page').strip('-').lower()
    stem = stem[:48] or 'ai-page'
    return f'{stem}-{secrets.token_hex(6)}.html'


def _ensure_html_document(html: str, title: str | None) -> str:
    content = html.strip()
    if len(content.encode('utf-8')) > MAX_HTML_PAGE_BYTES:
        raise ValueError('HTML content is too large')
    if re.search(r'<\s*script\b', content, flags=re.IGNORECASE):
        raise ValueError('Script tags are not allowed in generated HTML pages')
    if re.search(r'\son[a-z]+\s*=', content, flags=re.IGNORECASE):
        raise ValueError('Inline event handlers are not allowed in generated HTML pages')

    if '<html' in content.lower():
        return content

    safe_title = (title or 'AI 生成查询页').replace('<', '&lt;').replace('>', '&gt;')
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body>
{content}
</body>
</html>
"""


async def _get_all_attachment_entity_ids(entity_type: str) -> list[int]:
    normalized_type = attachment_download_service.normalize_type(entity_type)
    model = attachment_download_service._get_model(normalized_type)

    async with async_db_session() as db:
        stmt = select(model.id).where(model.file_url.is_not(None))
        if hasattr(model, 'parent_id'):
            stmt = stmt.where((model.parent_id.is_(None)) | (model.parent_id == 0))
        result = await db.execute(stmt.order_by(model.id.asc()))
        return [int(item) for item in result.scalars().all()]


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
        entity_ids: list[int] | None = None,
    ) -> str:
        """
        Prepare downloading original attachment files for business entities.

        Use this tool whenever the user asks to download, export, pack, or get attachments/files for business records.
        Requests such as "下载公司所有商标", "下载全部资质附件", or "打包专利文件" must use this tool, not HTML generation.
        If the user asks for all records of a supported entity type, omit entity_ids or pass an empty list.
        The frontend will use the returned action to download a ZIP file.
        Supported entity_type values include: qualification/company_qualification/资质/公司资质,
        patent/intellectual_property_patent/专利, trademark/intellectual_property_trademark/商标,
        software/intellectual_property_software/软件著作权/软件, credential/staff_credential/员工证件/证件.

        :param ctx: Run context
        :param entity_type: Business entity type
        :param entity_ids: Optional business entity IDs. Empty means all records with attachments.
        :return:
        """
        _ = ctx
        normalized_ids = [int(item) for item in entity_ids or [] if int(item) > 0]
        if not normalized_ids:
            normalized_ids = await _get_all_attachment_entity_ids(entity_type)
        if not normalized_ids:
            return json.dumps(
                {
                    'error': f'No attachment records found for entity type: {entity_type}',
                    'message': '未找到可下载附件的记录。',
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                'action': 'download_attachments',
                'entity_type': entity_type,
                'entity_ids': normalized_ids,
                'message': f'prepared to download {len(normalized_ids)} item attachments',
            },
            ensure_ascii=False,
        )

    @toolset.tool
    async def create_query_html_page(
        ctx: RunContext[ChatAgentDeps],
        title: str,
        html: str,
        description: str | None = None,
    ) -> str:
        """
        Create a static HTML query or presentation page and return preview/download metadata.

        Use this only when the user explicitly asks to create/generate an HTML page, web page, visual report page,
        preview page, QR-code-accessible page, or shareable page.
        Do not use this tool for requests to download business attachments or original files; use download_attachments instead.

        :param ctx: Run context
        :param title: Page title
        :param html: Complete HTML document or body HTML. Do not include script tags.
        :param description: Optional page description
        :return:
        """
        _ = ctx
        try:
            content = _ensure_html_document(html, title)
        except ValueError as e:
            return json.dumps({'error': str(e)}, ensure_ascii=False)

        filename = _normalize_html_page_filename(title)
        relative_path = f'{HTML_PAGE_DIR}/{filename}'
        output_dir = UPLOAD_DIR / HTML_PAGE_DIR
        await anyio.Path(output_dir).mkdir(parents=True, exist_ok=True)
        async with await anyio.open_file(output_dir / filename, mode='w', encoding='utf-8') as file:
            await file.write(content)

        url = f'/static/upload/{relative_path}'
        return json.dumps(
            {
                'action': 'show_html_page',
                'title': title,
                'description': description or '',
                'url': url,
                'download_url': url,
                'filename': filename,
                'message': 'HTML 页面已生成，可打开预览、下载或扫码访问。',
            },
            ensure_ascii=False,
        )

    return CapabilityResult(
        capability=Toolset(toolset),
        introduces_function_tool_source=True,
    )
