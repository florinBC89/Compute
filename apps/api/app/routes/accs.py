"""Accs: persistent named agent identities (Agent OS V0.4 slice, "give Acc
a name and a face").

Own top-level module rather than folded into app.routes.workspace --
Accs need a fuller create/list/get/patch surface, the same reason jobs
has its own module instead of living in workspace.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Acc, Project
from app.schemas.acc import (
    AccCreateRequest,
    AccDetail,
    AccList,
    AccPatchRequest,
    AccResponse,
)
from app.services.accs import acc_work_items, list_workspace_accs, to_acc_response
from app.services.user_scope import CurrentUser, resolve_current_user

router = APIRouter(prefix="/accs", tags=["accs"])


async def _owned_project(
    session: AsyncSession, project_id: uuid.UUID, current_user: CurrentUser
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    return project


async def _owned_acc(
    session: AsyncSession, acc_id: str, current_user: CurrentUser
) -> Acc:
    try:
        acc_uuid = uuid.UUID(acc_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="acc not found"
        ) from exc

    acc = await session.get(Acc, acc_uuid)
    if acc is None or acc.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="acc not found"
        )
    return acc


async def _project_name(session: AsyncSession, project_id: uuid.UUID) -> str:
    project = await session.get(Project, project_id)
    return project.name if project is not None else ""


@router.post("", response_model=AccResponse)
async def create_acc(
    body: AccCreateRequest,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccResponse:
    if not body.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="name is required"
        )
    try:
        project_uuid = uuid.UUID(body.project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        ) from exc
    project = await _owned_project(session, project_uuid, current_user)

    acc = Acc(
        id=uuid.uuid4(),
        workspace_id=current_user.workspace_id,
        project_id=project.id,
        name=body.name.strip(),
        goal=body.goal.strip() if body.goal else None,
    )
    session.add(acc)
    await session.flush()
    return to_acc_response(acc, project.name)


@router.get("", response_model=AccList)
async def list_accs(
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccList:
    accs = await list_workspace_accs(session, current_user.workspace_id)
    return AccList(
        accs=[
            to_acc_response(acc, await _project_name(session, acc.project_id))
            for acc in accs
        ]
    )


@router.get("/{acc_id}", response_model=AccDetail)
async def get_acc(
    acc_id: str,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccDetail:
    acc = await _owned_acc(session, acc_id, current_user)
    project_name = await _project_name(session, acc.project_id)
    work = await acc_work_items(session, acc.project_id)
    return AccDetail(**to_acc_response(acc, project_name).model_dump(), work=work)


@router.patch("/{acc_id}", response_model=AccResponse)
async def patch_acc(
    acc_id: str,
    body: AccPatchRequest,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccResponse:
    acc = await _owned_acc(session, acc_id, current_user)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="name is required"
            )
        acc.name = body.name.strip()
    if body.goal is not None:
        acc.goal = body.goal.strip() or None
    await session.flush()
    return to_acc_response(acc, await _project_name(session, acc.project_id))
