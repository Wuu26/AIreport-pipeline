"""Generic RSS fetcher using feedparser."""
from __future__ import annotations
from datetime import datetime, timezone
import logging
import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from ai_pipeline.models import RawItem
from ai_pipeline.config import RSS_SOURCES

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_rss_source(
    client: httpx.AsyncClient,
    name: str,
    url: str,
) -> list[RawItem]:
    """Fetch and parse a single RSS feed."""
    try:
        resp = await client.get(url, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception:
        # Try feedparser directly as fallback
        feed = feedparser.parse(url)

    items = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        # Parse published date
        published_at = _parse_date(entry)
        # Content: summary or content
        content = ""
        if hasattr(entry, "summary"):
            content = entry.summary or ""
        elif hasattr(entry, "content") and entry.content:
            content = entry.content[0].get("value", "")
        items.append(RawItem(
            title=title,
            url=link,
            source=name,
            published_at=published_at,
            content=content[:2000],  # cap length
        ))
    return items


def _parse_date(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


async def fetch_all_rss(client: httpx.AsyncClient) -> list[RawItem]:
    """Fetch all configured RSS sources (sequential to avoid hammering)."""
    items: list[RawItem] = []
    for name, url, _hint in RSS_SOURCES:
        try:
            results = await fetch_rss_source(client, name, url)
            items.extend(results)
        except Exception as e:
            logger.warning("RSS source %s failed: %s", name, e)
    return items
