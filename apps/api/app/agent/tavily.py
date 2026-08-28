"""Tavily web search (V0.2 human workspace, Phase 5).

Thin httpx client -- httpx is already a dependency
(apps/api/requirements.txt), no new package needed. Real sources for
`extract_facts` to build on, replacing Phase 4's model-only-knowledge
stand-in.
"""

from __future__ import annotations

import httpx

from app.config import get_settings

TAVILY_URL = "https://api.tavily.com/search"


async def search(query: str, *, max_results: int = 5) -> list[dict[str, str]]:
    settings = get_settings()
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            json={
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "topic": "general",
            },
        )
        response.raise_for_status()

    return [
        {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", ""),
        }
        for result in response.json().get("results", [])
    ]
