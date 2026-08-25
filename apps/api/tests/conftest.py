"""Test fixtures for the API.

Requires a real PostgreSQL: the schema uses JSONB, partial indexes and
``CHAR(64)`` columns, and testing reuse semantics against a different engine
would be testing something other than what ships.

    docker compose up -d postgres
    TEST_DATABASE_URL=postgresql+asyncpg://computelayer:computelayer@localhost:5432/computelayer_test \\
        pytest apps/api/tests -q
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import ApiKey, Base, Project, Workspace
from app.services.scope import hash_api_key

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://computelayer:computelayer@localhost:5432/computelayer_test",
)
TEST_API_KEY = "cl_test_conformance_key"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def engine():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from app.config import get_settings

    get_settings.cache_clear()

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(engine):
    """A workspace, a project and a project-scoped API key."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        workspace = Workspace(id=uuid.uuid4(), name="test")
        session.add(workspace)
        await session.flush()

        project = Project(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            name="conformance",
            slug="conformance",
        )
        session.add(project)
        await session.flush()

        api_key = ApiKey(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            project_id=project.id,
            name="test",
            key_prefix=TEST_API_KEY[:12],
            key_hash=hash_api_key(TEST_API_KEY),
        )
        session.add(api_key)
        await session.commit()
    return {"api_key": TEST_API_KEY, "project": "conformance"}


@pytest_asyncio.fixture
async def http_client(engine, seeded):
    """An httpx client wired straight into the ASGI app -- no sockets."""
    import app.db as db

    db._engine = engine
    db._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    from app.main import app as fastapi_app

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://testserver/v1",
        headers={"Authorization": f"Bearer {seeded['api_key']}"},
    ) as client:
        yield client

    await db.dispose_engine()


@pytest_asyncio.fixture
async def cl(http_client, seeded):
    """A ComputeLayer client talking to the real API over ASGI."""
    from computelayer import ComputeLayer
    from computelayer.transport import HttpTransport

    transport = HttpTransport(
        api_key=seeded["api_key"],
        base_url="http://testserver/v1",
        project=seeded["project"],
        client=http_client,
    )
    client = ComputeLayer(project=seeded["project"], transport=transport)
    yield client
