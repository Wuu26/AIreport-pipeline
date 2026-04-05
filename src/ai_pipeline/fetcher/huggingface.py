"""HuggingFace Papers fetcher — scrapes huggingface.co/papers."""
from __future__ import annotations
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
from ai_pipeline.models import RawItem

HF_PAPERS_URL = "https://huggingface.co/papers"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_huggingface(client: httpx.AsyncClient) -> list[RawItem]:
    """Scrape trending papers from HuggingFace Papers page."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ai-pipeline-bot/1.0)"}
    resp = await client.get(HF_PAPERS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return _parse_hf_html(resp.text)


def _parse_hf_html(html: str) -> list[RawItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    # HF papers page: each paper is an <article> or <h3> with a link
    # Try multiple selectors since HF's markup changes occasionally
    for article in soup.select("article"):
        title_el = article.find("h3") or article.find("h2")
        link_el = article.find("a", href=True)
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://huggingface.co{href}"
        # Try to get upvote count
        upvotes = 0
        for el in article.find_all(["button", "span", "div"]):
            text = el.get_text(strip=True)
            if text.isdigit():
                upvotes = max(upvotes, int(text))
        if title and url:
            items.append(RawItem(
                title=title,
                url=url,
                source="huggingface",
                published_at=datetime.now(timezone.utc),
                content="",
                upvotes=upvotes,
            ))
    return items
