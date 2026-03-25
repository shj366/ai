import base64
import json

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic_ai import (
    Agent,
    BinaryContent,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    NativeOutput,
    PromptedOutput,
    RunContext,
    TextPart,
    ToolOutput,
    UserPromptPart,
)
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import AudioUrl, DocumentUrl, ImageUrl, VideoUrl
from pydantic_ai.models import Model
from pydantic_core import to_jsonable_python
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import uuid4_str
from backend.plugin.ai.crud.crud_chat_history import ai_chat_history_dao
from backend.plugin.ai.crud.crud_chat_message import ai_chat_message_dao
from backend.plugin.ai.crud.crud_model import ai_model_dao
from backend.plugin.ai.crud.crud_provider import ai_provider_dao
from backend.plugin.ai.enums import (
    AIChatAttachmentSourceType,
    AIChatAttachmentType,
    AIChatMessageRoleType,
    AIChatOutputModeType,
)
from backend.plugin.ai.schema.chat import AIChatParam
from backend.plugin.ai.schema.chat_history import CreateAIChatHistoryParam, UpdateAIChatHistoryParam
from backend.plugin.ai.service.chat_history_service import ai_chat_history_service
from backend.plugin.ai.service.mcp_service import mcp_service
from backend.plugin.ai.utils.chat_control import build_model_settings
from backend.plugin.ai.utils.message_parse import (
    build_chat_transcript,
    make_chat_message,
    serialize_model_messages,
    to_chat_messages_by_parts,
)
from backend.plugin.ai.utils.model_control import get_pydantic_model


class ChatService:
    """聊天服务类"""

    @dataclass(slots=True)
    class ChatAgentDeps:
        """聊天代理依赖"""

        db: AsyncSession
        user_id: int

    class StructuredOutputBase(BaseModel):
        """结构化输出基础模型"""

        model_config = ConfigDict(extra='forbid')

    @classmethod
    def _build_object_schema_type(cls, properties: dict[str, Any], required: set[str], *, model_name: str) -> Any:
        fields: dict[str, tuple[Any, Any]] = {}
        for field_name, field_schema in properties.items():
            field_type = cls._build_schema_type(field_schema, model_name=f'{model_name}{field_name.title()}')
            if field_name in required:
                fields[field_name] = (field_type, Field(description=field_schema.get('description', field_name)))
            else:
                fields[field_name] = (
                    field_type | None,
                    Field(default=None, description=field_schema.get('description', field_name)),
                )
        if not fields:
            return dict[str, Any]
        return create_model(model_name, __base__=cls.StructuredOutputBase, **fields)

    @classmethod
    def _build_union_schema_type(cls, items: list[dict[str, Any]], *, model_name: str) -> Any:
        variants = [cls._build_schema_type(item, model_name=f'{model_name}Variant') for item in items]
        if not variants:
            return Any
        variant_type = variants[0]
        for item in variants[1:]:
            variant_type = variant_type | item
        return variant_type

    @staticmethod
    def _build_scalar_schema_type(schema_type: Any) -> Any:
        if schema_type == 'string':
            return str
        if schema_type == 'integer':
            return int
        if schema_type == 'number':
            return float
        if schema_type == 'boolean':
            return bool
        if schema_type == 'null':
            return None
        return None

    @classmethod
    def _build_schema_type(cls, schema: dict[str, Any], *, model_name: str) -> Any:
        schema_type = schema.get('type')
        if isinstance(schema_type, list):
            non_null_types = [item for item in schema_type if item != 'null']
            if len(non_null_types) == 1:
                return cls._build_schema_type({**schema, 'type': non_null_types[0]}, model_name=model_name) | None
            return Any

        scalar_type = cls._build_scalar_schema_type(schema_type)
        if scalar_type is not None:
            return scalar_type
        if schema_type == 'array':
            item_schema = schema.get('items', {})
            return list[cls._build_schema_type(item_schema, model_name=f'{model_name}Item')]
        if schema_type == 'object' or 'properties' in schema:
            return cls._build_object_schema_type(
                schema.get('properties', {}),
                set(schema.get('required', [])),
                model_name=model_name,
            )
        if 'anyOf' in schema:
            return cls._build_union_schema_type(schema['anyOf'], model_name=model_name)
        return Any

    @classmethod
    async def _stream_response_messages(
        cls,
        *,
        result: Any,
        conversation_id: str,
        start_message_index: int,
        include_thinking: bool,
    ) -> AsyncGenerator[bytes, Any]:
        emitted_content: dict[tuple[int, AIChatMessageRoleType], str] = {}
        async for response, _ in result.stream_responses(debounce_by=0.01):
            try:
                snapshot_messages = to_chat_messages_by_parts(
                    response,
                    start_message_index=start_message_index,
                    conversation_id=conversation_id,
                )
            except errors.NotFoundError:
                continue
            for snapshot_message in snapshot_messages:
                if not include_thinking and snapshot_message['role'] == AIChatMessageRoleType.thinking:
                    continue
                message_key = (snapshot_message['message_index'], snapshot_message['role'])
                previous_content = emitted_content.get(message_key)
                if previous_content == snapshot_message['content']:
                    continue
                emitted_content[message_key] = snapshot_message['content']
                yield json.dumps(snapshot_message, ensure_ascii=False).encode('utf-8') + b'\n'

    @classmethod
    def _build_output_type(cls, *, chat: AIChatParam) -> Any:
        if chat.output_mode == AIChatOutputModeType.text:
            return str
        if not chat.output_schema:
            raise errors.RequestError(msg='结构化输出模式必须提供 output_schema')

        schema_type = cls._build_schema_type(
            chat.output_schema,
            model_name=chat.output_schema_name or 'ChatStructuredOutput',
        )
        if chat.output_mode == AIChatOutputModeType.tool:
            return ToolOutput(schema_type, name=chat.output_schema_name, description=chat.output_schema_description)
        if chat.output_mode == AIChatOutputModeType.native:
            return NativeOutput(schema_type, name=chat.output_schema_name)
        if chat.output_mode == AIChatOutputModeType.prompted:
            return PromptedOutput(schema_type, name=chat.output_schema_name, description=chat.output_schema_description)
        raise errors.RequestError(msg='不支持的输出模式')

    @classmethod
    def _build_agent(
        cls,
        *,
        model: Model,
        output_type: Any,
        toolsets: list[Any],
        enable_builtin_tools: bool,
    ) -> Agent[Any, Any]:
        agent = Agent(
            name='fba_chat',
            deps_type=cls.ChatAgentDeps,
            model=model,
            output_type=output_type,
            toolsets=toolsets,
        )

        if enable_builtin_tools:

            @agent.tool
            def get_current_time(_: RunContext[ChatService.ChatAgentDeps]) -> str:
                """获取当前时间"""
                from backend.utils.timezone import timezone

                return timezone.now().isoformat()

            @agent.tool
            async def list_my_quick_phrases(ctx: RunContext[ChatService.ChatAgentDeps]) -> list[dict[str, Any]]:
                """获取当前用户快捷短语列表"""
                from backend.plugin.ai.service.quick_phrase_service import ai_quick_phrase_service

                phrases = await ai_quick_phrase_service.get_all(db=ctx.deps.db, user_id=ctx.deps.user_id)
                return [{'id': item.id, 'title': item.title, 'content': item.content} for item in phrases]

            @agent.tool
            async def list_provider_models(ctx: RunContext[ChatService.ChatAgentDeps], provider_id: int) -> list[str]:
                """获取指定供应商可用模型 ID"""
                models = await ai_model_dao.get_all(ctx.deps.db, provider_id=provider_id)
                return [item.model_id for item in models if item.status]

        return agent

    @classmethod
    async def stream_messages(  # noqa: C901
        cls,
        *,
        db: AsyncSession,
        chat: AIChatParam,
        user_id: int,
    ) -> AsyncGenerator[bytes, Any]:
        """
        流式消息

        :param db: 数据库会话
        :param chat: 聊天参数
        :param user_id: 用户 ID
        :return:
        """
        provider = await ai_provider_dao.get(db, chat.provider_id)
        if not provider:
            raise errors.NotFoundError(msg='供应商不存在')
        if not provider.status:
            raise errors.RequestError(msg='此供应商暂不可用，请更换供应商或联系系统管理员')

        model = await ai_model_dao.get_by_model_and_provider(db, chat.model_id, chat.provider_id)
        if not model:
            raise errors.NotFoundError(msg='供应商模型不存在')
        if not model.status:
            raise errors.RequestError(msg='此模型暂不可用，请更换模型或联系系统管理员')

        conversation_id = chat.conversation_id or uuid4_str()
        chat_history = None
        existing_message_rows = []
        message_history = []
        next_message_index = 0
        prompt = chat.user_prompt
        should_emit_user_message = True
        if chat.conversation_id:
            chat_history = await ai_chat_history_service.get_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )
            existing_message_rows = list(await ai_chat_message_dao.get_all(db, conversation_id))
            if chat.edit_message_id is not None and chat.regenerate_message_id is not None:
                raise errors.RequestError(msg='编辑重发与重新生成不能同时使用')
            if chat.edit_message_id is not None:
                if prompt is None:
                    raise errors.RequestError(msg='编辑重发时用户提示词不能为空')
                chat_history, _, message_history = await ai_chat_history_service.get_editable_message(
                    db=db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message_id=chat.edit_message_id,
                )
            elif chat.regenerate_message_id is not None:
                chat_history, prompt, message_history = await ai_chat_history_service.get_regeneratable_message(
                    db=db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message_id=chat.regenerate_message_id,
                )
                should_emit_user_message = False
            else:
                if prompt is None:
                    raise errors.RequestError(msg='用户提示词不能为空')
                message_history = (
                    ModelMessagesTypeAdapter.validate_python([row.message for row in existing_message_rows])
                    if existing_message_rows
                    else []
                )
            next_message_index = len(build_chat_transcript(message_history, conversation_id=conversation_id))
        else:
            if chat.edit_message_id is not None:
                raise errors.RequestError(msg='编辑重发必须指定会话 ID')
            if chat.regenerate_message_id is not None:
                raise errors.RequestError(msg='重新生成必须指定会话 ID')
            if prompt is None:
                raise errors.RequestError(msg='用户提示词不能为空')
        assert prompt is not None

        attachments: list[Any] = []
        for attachment in chat.attachments or []:
            if attachment.source_type == AIChatAttachmentSourceType.url:
                if not attachment.url:
                    raise errors.RequestError(msg='URL 类型附件必须提供 url')
                url = str(attachment.url)
                if attachment.type == AIChatAttachmentType.image:
                    attachments.append(ImageUrl(url))
                elif attachment.type == AIChatAttachmentType.audio:
                    attachments.append(AudioUrl(url))
                elif attachment.type == AIChatAttachmentType.video:
                    attachments.append(VideoUrl(url))
                else:
                    attachments.append(DocumentUrl(url))
                continue

            if not attachment.content:
                raise errors.RequestError(msg='Base64 类型附件必须提供 content')
            if not attachment.media_type:
                raise errors.RequestError(msg='Base64 类型附件必须提供 media_type')
            attachments.append(
                BinaryContent(
                    data=base64.b64decode(attachment.content),
                    media_type=attachment.media_type,
                )
            )
        user_input = [prompt, *attachments] if attachments else prompt

        async def _save_history(messages: list[dict[str, object]]) -> None:
            title = chat_history.title if chat_history else ' '.join(prompt.split())
            if not title:
                title = '新会话'
            elif len(title) > 256:
                title = title[:253] + '...'
            payload = {
                'conversation_id': conversation_id,
                'title': title,
                'provider_id': chat.provider_id,
                'model_id': chat.model_id,
                'user_id': chat_history.user_id if chat_history else user_id,
                'pinned_time': chat_history.pinned_time if chat_history else None,
            }
            if chat_history:
                await ai_chat_history_dao.update(db, chat_history.id, UpdateAIChatHistoryParam(**payload))
            else:
                await ai_chat_history_dao.create(db, CreateAIChatHistoryParam(**payload))
            await ai_chat_message_dao.delete(db, conversation_id)
            if messages:
                await ai_chat_message_dao.bulk_create(
                    db,
                    [
                        {
                            'conversation_id': conversation_id,
                            'provider_id': existing_message_rows[index].provider_id
                            if index < len(message_history) and index < len(existing_message_rows)
                            else chat.provider_id,
                            'model_id': existing_message_rows[index].model_id
                            if index < len(message_history) and index < len(existing_message_rows)
                            else chat.model_id,
                            'message_index': index,
                            'message': message,
                        }
                        for index, message in enumerate(messages)
                    ],
                )

        if should_emit_user_message:
            yield (
                json.dumps(
                    make_chat_message(
                        message_index=next_message_index,
                        role=AIChatMessageRoleType.user,
                        content=prompt,
                        conversation_id=conversation_id,
                    ),
                    ensure_ascii=False,
                ).encode('utf-8')
                + b'\n'
            )

        model_settings = build_model_settings(chat=chat, provider_type=provider.type)
        output_type = cls._build_output_type(chat=chat)
        toolsets = await mcp_service.get_toolsets(db=db, mcp_ids=chat.mcp_ids) if chat.mcp_ids else []
        model_instance = get_pydantic_model(
            provider_type=provider.type,
            model_name=model.model_id,
            api_key=provider.api_key,
            base_url=provider.api_host,
            model_settings=model_settings,
            provider_name=provider.name,
        )
        agent = cls._build_agent(
            model=model_instance,
            output_type=output_type,
            toolsets=toolsets,
            enable_builtin_tools=chat.enable_builtin_tools,
        )
        run_kwargs: dict[str, Any] = {
            'deps': cls.ChatAgentDeps(db=db, user_id=user_id),
        }
        if message_history:
            run_kwargs['message_history'] = message_history

        for attempt in range(settings.AI_CHAT_MAX_RETRIES + 1):
            try:
                async with agent.run_stream(user_input, **run_kwargs) as result:
                    if chat.output_mode == AIChatOutputModeType.text:
                        async for chunk in cls._stream_response_messages(
                            result=result,
                            conversation_id=conversation_id,
                            start_message_index=next_message_index + (1 if should_emit_user_message else 0),
                            include_thinking=chat.include_thinking,
                        ):
                            yield chunk
                        await _save_history(serialize_model_messages(result.all_messages()))
                    else:
                        structured_output = await result.get_output()
                        serialized_output = to_jsonable_python(structured_output)
                        if not isinstance(serialized_output, (dict, list)):
                            serialized_output = {'value': serialized_output}
                        structured_response = ModelResponse(
                            parts=[TextPart(json.dumps(serialized_output, ensure_ascii=False))],
                            model_name=model.model_id,
                            metadata={'structured_data': serialized_output},
                        )
                        yield (
                            json.dumps(
                                make_chat_message(
                                    message_index=next_message_index + (1 if should_emit_user_message else 0),
                                    role=AIChatMessageRoleType.model,
                                    content=structured_response.parts[0].content,
                                    conversation_id=conversation_id,
                                    structured_data=structured_response.metadata['structured_data'],
                                ),
                                ensure_ascii=False,
                            ).encode('utf-8')
                            + b'\n'
                        )
                        persisted_messages = [*message_history]
                        if should_emit_user_message:
                            persisted_messages.append(ModelRequest(parts=[UserPromptPart(prompt)]))
                        persisted_messages.append(structured_response)
                        await _save_history(serialize_model_messages(persisted_messages))
                break
            except UnexpectedModelBehavior as e:
                if attempt < settings.AI_CHAT_MAX_RETRIES:
                    log.warning(
                        f'聊天模型响应异常，准备重试: conversation_id={conversation_id}, '
                        f'attempt={attempt + 1}, error={e}'
                    )
                    continue
                log.warning(f'聊天模型响应异常，已降级为错误提示: conversation_id={conversation_id}, error={e}')
                failure_message = '服务暂时不可用，请稍后再试'
                failure_response = ModelResponse(
                    parts=[TextPart(failure_message)],
                    model_name=model.model_id,
                    metadata={
                        'is_error': True,
                        'error_message': str(e),
                    },
                )
                persisted_messages = [*message_history]
                if should_emit_user_message:
                    persisted_messages.append(ModelRequest(parts=[UserPromptPart(prompt)]))
                persisted_messages.append(failure_response)
                yield (
                    json.dumps(
                        make_chat_message(
                            message_index=next_message_index + (1 if should_emit_user_message else 0),
                            role=AIChatMessageRoleType.model,
                            content=failure_message,
                            conversation_id=conversation_id,
                            is_error=True,
                            error_message=str(e),
                        ),
                        ensure_ascii=False,
                    ).encode('utf-8')
                    + b'\n'
                )
                await _save_history(serialize_model_messages(persisted_messages))
                break


ai_chat_service: ChatService = ChatService()
