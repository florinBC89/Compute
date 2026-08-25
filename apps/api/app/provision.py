"""Provision one invited person a workspace, project and API key.

Interim to real self-serve signup (spec V0.1 has none -- §1 excludes billing
and enterprise account management entirely). Run by hand, once per invite:

    python -m app.provision --name "Jane's Team" --project research-agent

Idempotent on workspace name: running it again for the same name reuses the
workspace and project, but always mints a *new* API key -- there is no
"existing key" to find, since each invite should get its own credential to
revoke independently later.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.db import dispose_engine, get_sessionmaker
from app.models import ApiKey, Project, Workspace
from app.services.scope import KEY_PREFIX_LENGTH, generate_api_key, hash_api_key


def _slugify(value: str) -> str:
    return "-".join(value.strip().lower().split()) or "default"


async def provision(workspace_name: str, project_slug: str) -> str:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        workspace = (
            await session.execute(
                select(Workspace).where(Workspace.name == workspace_name)
            )
        ).scalars().first()
        if workspace is None:
            workspace = Workspace(id=uuid.uuid4(), name=workspace_name)
            session.add(workspace)
            await session.flush()

        project = (
            await session.execute(
                select(Project).where(
                    Project.workspace_id == workspace.id,
                    Project.slug == project_slug,
                )
            )
        ).scalars().first()
        if project is None:
            project = Project(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                name=project_slug,
                slug=project_slug,
            )
            session.add(project)
            await session.flush()

        plaintext = generate_api_key("live")
        session.add(
            ApiKey(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                project_id=project.id,
                name=f"invite for {workspace_name}",
                key_prefix=plaintext[:KEY_PREFIX_LENGTH],
                key_hash=hash_api_key(plaintext),
            )
        )
        await session.commit()

    return plaintext


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="workspace name, e.g. the person or team's name")
    parser.add_argument("--project", default="default", help="project slug (default: 'default')")
    args = parser.parse_args()

    project_slug = _slugify(args.project)
    key = await provision(args.name, project_slug)
    await dispose_engine()

    print(
        "Provisioned.\n"
        f"  workspace : {args.name}\n"
        f"  project   : {project_slug}\n"
        f"  api key   : {key}\n\n"
        "Send them:\n"
        "  export COMPUTELAYER_API_URL=<your deployed API url>/v1\n"
        f"  export COMPUTELAYER_API_KEY={key}\n"
        f"  export COMPUTELAYER_PROJECT={project_slug}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
