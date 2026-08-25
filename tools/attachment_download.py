import json

from pydantic_ai import RunContext
from sqlalchemy import select

from backend.database.db import async_db_session
from backend.plugin.ai.dataclasses import ChatAgentDeps
from backend.plugin.attachment_export.core.attachment_download import attachment_download_service


async def _get_all_attachment_entity_ids(entity_type: str) -> list[int]:
    normalized_type = attachment_download_service.normalize_type(entity_type)
    model = attachment_download_service._get_model(normalized_type)

    async with async_db_session() as db:
        stmt = select(model.id).where(model.file_url.is_not(None))
        if hasattr(model, 'deleted'):
            stmt = stmt.where(model.deleted == 0)
        if hasattr(model, 'parent_id'):
            stmt = stmt.where((model.parent_id.is_(None)) | (model.parent_id == 0))
        result = await db.execute(stmt.order_by(model.id.asc()))
        return [int(item) for item in result.scalars().all()]


async def download_attachments(
    ctx: RunContext[ChatAgentDeps],
    entity_type: str,
    entity_ids: list[int] | None = None,
) -> str:
    """
    Download original attachment files for business records as a ZIP archive.

    Always use this tool for requests such as downloading, exporting, packing, or
    obtaining all patent, trademark, qualification, software copyright, or staff
    credential attachments. Do not answer with an explanation about public or
    global databases, and do not create an HTML page for these requests.

    :param ctx: Current authenticated chat context.
    :param entity_type: Entity type, for example patent, trademark, qualification,
        software, or credential. Chinese names are also accepted.
    :param entity_ids: Optional entity IDs. Omit this argument to download all
        records of the selected entity type that have attachments.
    :return: A download action consumed by the chat frontend.
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
