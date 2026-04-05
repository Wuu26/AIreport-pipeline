"""Fetcher package — parallel async entry point."""
from __future__ import annotations
import asyncio
import logging
import httpx
from ai_pipeline.models import RawItem
from .arxiv import fetch_arxiv
from .huggingface import fetch_huggingface
from .rss import fetch_all_rss
from .websearch import fetch_websearch

logger = logging.getLogger(__name__)


async def fetch_all() -> list[RawItem]:
    """Fetch from all sources in parallel, deduplicate by URL."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            fetch_arxiv(client),
            fetch_huggingface(client),
            fetch_all_rss(client),
            fetch_websearch(client),
            return_exceptions=True,
        )
    items: list[RawItem] = []
    source_names = ["arxiv", "huggingface", "rss", "websearch"]
    for name, result in zip(source_names, results):
        if isinstance(result, list):
            items.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Fetcher %s failed: %s", name, result)

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[RawItem] = []
    for item in items:
        if item.url not in seen:
            seen.add(item.url)
            unique.append(item)
    return unique
