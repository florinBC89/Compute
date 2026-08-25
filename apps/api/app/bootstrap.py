"""Create the local workspace, project and API key (spec §54).

    python -m app.bootstrap

Idempotent: running it twice does not create duplicates and does not rotate an
existing key.
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.models import ApiKey, Project, Workspace
from app.services.scope import KEY_PREFIX_LENGTH, generate_api_key, hash_api_key


async def bootstrap() -> str:
    settings = get_settings()
    plaintext = settings.bootstrap_api_key or generate_api_key("test")

    async with get_sessionmaker()() as session:
        workspace = (
            await session.execute(
                select(Workspace).where(Workspace.name == settings.bootstrap_workspace)
            )
        ).scalars().first()
        if workspace is None:
            workspace = Workspace(id=uuid.uuid4(), name=settings.bootstrap_workspace)
            session.add(workspace)
            await session.flush()

        project = (
            await session.execute(
                select(Project).where(
                    Project.workspace_id == workspace.id,
                    Project.slug == settings.bootstrap_project,
                )
            )
        ).scalars().first()
        if project is None:
            project = Project(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                name=settings.bootstrap_project,
                slug=settings.bootstrap_project,
            )
            session.add(project)
            await session.flush()

        key_hash = hash_api_key(plaintext)
        existing = (
            await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
        ).scalars().first()
        if existing is None:
            session.add(
                ApiKey(
                    id=uuid.uuid4(),
                    workspace_id=workspace.id,
                    project_id=project.id,
                    name="local development",
                    key_prefix=plaintext[:KEY_PREFIX_LENGTH],
                    key_hash=key_hash,
                )
            )

        await session.commit()

    return plaintext


async def _main() -> None:
    settings = get_settings()
    key = await bootstrap()
    await dispose_engine()
    print(
        "ComputeLayer is ready.\n"
        f"  workspace : {settings.bootstrap_workspace}\n"
        f"  project   : {settings.bootstrap_project}\n"
        f"  api key   : {key}\n\n"
        "  export COMPUTELAYER_API_URL=http://localhost:8000/v1\n"
        f"  export COMPUTELAYER_API_KEY={key}\n"
        f"  export COMPUTELAYER_PROJECT={settings.bootstrap_project}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
