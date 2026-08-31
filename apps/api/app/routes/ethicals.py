"""Ethicals: persistent named agent identities (Agent OS V0.4 slice, "give Ethical
a name and a face").

Own top-level module rather than folded into app.routes.workspace --
Ethicals need a fuller create/list/get/patch surface, the same reason jobs
has its own module instead of living in workspace.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ethical, Project
from app.schemas.ethical import (
    EthicalCreateRequest,
    EthicalDetail,
    EthicalList,
    EthicalPatchRequest,
    EthicalResponse,
)
from app.services.ethicals import ethical_work_items, list_workspace_ethicals, to_ethical_response
from app.services.user_scope import CurrentUser, resolve_current_user

router = APIRouter(prefix="/ethicals", tags=["ethicals"])


async def _owned_project(
    session: AsyncSession, project_id: uuid.UUID, current_user: CurrentUser
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="project not found"
        )
    return project


async def _owned_ethical(
    session: AsyncSession, ethical_id: str, current_user: CurrentUser
) -> Ethical:
    try:
        ethical_uuid = uuid.UUID(ethical_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ethical not found"
        ) from exc

    ethical = await session.get(Ethical, ethical_uuid)
    if ethical is None or ethical.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ethical not found"
        )
    return ethical


async def _project_name(session: AsyncSession, project_id: uuid.UUID) -> str:
    project = await session.get(Project, project_id)
    return project.name if project is not None else ""


@router.post("", response_model=EthicalResponse)
async def create_ethical(
    body: EthicalCreateRequest,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> EthicalResponse:
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

    ethical = Ethical(
        id=uuid.uuid4(),
        workspace_id=current_user.workspace_id,
        project_id=project.id,
        name=body.name.strip(),
        goal=body.goal.strip() if body.goal else None,
    )
    session.add(ethical)
    await session.flush()
    return to_ethical_response(ethical, project.name)


@router.get("", response_model=EthicalList)
async def list_ethicals(
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> EthicalList:
    ethicals = await list_workspace_ethicals(session, current_user.workspace_id)
    return EthicalList(
        ethicals=[
            to_ethical_response(ethical, await _project_name(session, ethical.project_id))
            for ethical in ethicals
        ]
    )


@router.get("/{ethical_id}", response_model=EthicalDetail)
async def get_ethical(
    ethical_id: str,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> EthicalDetail:
    ethical = await _owned_ethical(session, ethical_id, current_user)
    project_name = await _project_name(session, ethical.project_id)
    work = await ethical_work_items(session, ethical.project_id)
    return EthicalDetail(**to_ethical_response(ethical, project_name).model_dump(), work=work)


@router.patch("/{ethical_id}", response_model=EthicalResponse)
async def patch_ethical(
    ethical_id: str,
    body: EthicalPatchRequest,
    current_user: CurrentUser = Depends(resolve_current_user),
    session: AsyncSession = Depends(get_session),
) -> EthicalResponse:
    ethical = await _owned_ethical(session, ethical_id, current_user)
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="name is required"
            )
        ethical.name = body.name.strip()
    if body.goal is not None:
        ethical.goal = body.goal.strip() or None
    await session.flush()
    return to_ethical_response(ethical, await _project_name(session, ethical.project_id))
