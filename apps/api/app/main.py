"""ComputeLayer API (spec §28).

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import dispose_engine
from app.routes import (
    artifact_policies,
    computations,
    cross_model,
    ethicals,
    jobs,
    me,
    metrics,
    resources,
    runs,
    workspace,
)
from app.services.locks import close_redis, get_redis

logger = logging.getLogger("computelayer.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    redis = await get_redis()
    if redis is None and settings.redis_url:
        # Redis is an optimization only (§37) -- log and carry on.
        logger.warning("redis unavailable; running without the hot cache")
    yield
    await close_redis()
    await dispose_engine()


app = FastAPI(
    title="ComputeLayer",
    version="0.1.0",
    summary="Deterministic incremental compute for AI agents",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(computations.router, prefix="/v1")
app.include_router(resources.router, prefix="/v1")
app.include_router(runs.router, prefix="/v1")
app.include_router(metrics.router, prefix="/v1")
app.include_router(artifact_policies.router, prefix="/v1")
app.include_router(cross_model.router, prefix="/v1")
app.include_router(me.router, prefix="/v1")
app.include_router(jobs.router, prefix="/v1")
app.include_router(workspace.router, prefix="/v1")
app.include_router(ethicals.router, prefix="/v1")


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
