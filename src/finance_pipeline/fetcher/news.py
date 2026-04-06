"""Finance news fetcher via RSS."""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from finance_pipeline.models import NewsItem
from finance_pipeline.config import FINANCE_RSS_SOURCES, NEWS_MAX_AGE_HOURS

logger = logging.getLogger(__name__)


def _parse_date(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
async def _fetch_one(client: httpx.AsyncClient, name: str, url: str) -> list[NewsItem]:
    """Fetch and parse a single RSS feed."""
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True,
                                headers={"User-Agent": "FinancePipeline/1.0"})
        feed = feedparser.parse(resp.text)
    except Exception:
        feed = feedparser.parse(url)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_MAX_AGE_HOURS)
    items = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue
        pub = _parse_date(entry)
        if pub < cutoff:
            continue
        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary or ""
        items.append(NewsItem(
            title=title,
            url=link,
            source=name,
            published_at=pub,
            summary=summary[:500],
        ))
    return items


async def fetch_finance_news(client: httpx.AsyncClient) -> list[NewsItem]:
    """Fetch from all configured finance RSS sources."""
    items: list[NewsItem] = []
    for name, url in FINANCE_RSS_SOURCES:
        try:
            results = await _fetch_one(client, name, url)
            items.extend(results)
            logger.info("News %s: %d items", name, len(results))
        except Exception as e:
            logger.warning("News source %s failed: %s", name, e)
    # Deduplicate by URL, sort by date desc, cap at 15
    seen: set[str] = set()
    unique = []
    for item in sorted(items, key=lambda x: x.published_at, reverse=True):
        if item.url not in seen:
            seen.add(item.url)
            unique.append(item)
    return unique[:15]
