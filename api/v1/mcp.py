from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.ai.schema.mcp import CreateAIMcpParam, GetAIMcpDetail, UpdateAIMcpParam
from backend.plugin.ai.service.mcp_service import ai_mcp_service

router = APIRouter()


@router.get('/all', summary='获取所有 MCP', dependencies=[DependsJwtAuth])
async def get_all_ai_mcps(request: Request, db: CurrentSession) -> ResponseSchemaModel[list[GetAIMcpDetail]]:
    data = await ai_mcp_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取 MCP 详情', dependencies=[DependsJwtAuth])
async def get_ai_mcp(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='MCP ID')],
) -> ResponseSchemaModel[GetAIMcpDetail]:
    data = await ai_mcp_service.get(db=db, pk=pk, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取所有 MCP',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_ai_mcps_paginated(
    request: Request,
    db: CurrentSession,
    name: Annotated[str | None, Query(description='MCP 名称')] = None,
    type: Annotated[int | None, Query(description='MCP 类型')] = None,
) -> ResponseSchemaModel[PageData[GetAIMcpDetail]]:
    page_data = await ai_mcp_service.get_list(db=db, user_id=request.user.id, name=name, type=type)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建 MCP',
    dependencies=[
        Depends(RequestPermission('ai:mcp:add')),
        DependsRBAC,
    ],
)
async def create_ai_mcp(request: Request, db: CurrentSessionTransaction, obj: CreateAIMcpParam) -> ResponseModel:
    await ai_mcp_service.create(
        db=db,
        obj=obj,
        user_id=request.user.id,
        is_superuser=request.user.is_superuser,
    )
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新 MCP',
    dependencies=[
        Depends(RequestPermission('ai:mcp:edit')),
        DependsRBAC,
    ],
)
async def update_ai_mcp(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='MCP ID')],
    obj: UpdateAIMcpParam,
) -> ResponseModel:
    count = await ai_mcp_service.update(
        db=db,
        pk=pk,
        obj=obj,
        user_id=request.user.id,
        is_superuser=request.user.is_superuser,
    )
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除 MCP',
    dependencies=[
        Depends(RequestPermission('ai:mcp:del')),
        DependsRBAC,
    ],
)
async def delete_ai_mcp(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='MCP ID')],
) -> ResponseModel:
    count = await ai_mcp_service.delete(db=db, pk=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()
