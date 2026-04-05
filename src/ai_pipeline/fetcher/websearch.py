"""Web search fetcher — uses DuckDuckGo HTML search as fallback."""
from __future__ import annotations
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from ai_pipeline.models import RawItem

SEARCH_QUERIES = [
    "AI research papers today 2026",
    "artificial intelligence news today",
    "中国AI新闻 今天",
]

DDG_URL = "https://html.duckduckgo.com/html/"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=8))
async def _ddg_search(client: httpx.AsyncClient, query: str) -> list[RawItem]:
    """Single DuckDuckGo HTML search."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ai-pipeline-bot/1.0)",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = await client.post(DDG_URL, data={"q": query}, headers=headers, timeout=20)
    if resp.status_code != 200:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    for result in soup.select(".result")[:5]:
        title_el = result.select_one(".result__title")
        link_el = result.select_one(".result__url")
        snippet_el = result.select_one(".result__snippet")
        if not title_el:
            continue
        link_tag = title_el.find("a", href=True)
        url = link_tag["href"] if link_tag else ""
        if not url or url.startswith("//duckduckgo"):
            continue
        items.append(RawItem(
            title=title_el.get_text(strip=True),
            url=url,
            source="websearch",
            published_at=datetime.now(timezone.utc),
            content=snippet_el.get_text(strip=True) if snippet_el else "",
        ))
    return items


async def fetch_websearch(client: httpx.AsyncClient) -> list[RawItem]:
    """Run all search queries and return combined results."""
    items: list[RawItem] = []
    for query in SEARCH_QUERIES:
        try:
            results = await _ddg_search(client, query)
            items.extend(results)
        except Exception:
            pass
    return items
