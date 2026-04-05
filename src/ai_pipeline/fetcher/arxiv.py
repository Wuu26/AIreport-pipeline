"""arXiv API fetcher."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from ai_pipeline.models import RawItem
from ai_pipeline.config import ARXIV_CATEGORIES, ARXIV_MAX_RESULTS

ARXIV_API_URL = "https://export.arxiv.org/api/query"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_arxiv(client: httpx.AsyncClient) -> list[RawItem]:
    """Fetch recent papers from arXiv API."""
    query = " OR ".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": ARXIV_MAX_RESULTS,
    }
    resp = await client.get(ARXIV_API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return _parse_arxiv_xml(resp.text)


def _parse_arxiv_xml(xml_text: str) -> list[RawItem]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    items = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        id_el = entry.find("atom:id", ns)
        summary_el = entry.find("atom:summary", ns)
        published_el = entry.find("atom:published", ns)
        if title_el is None or id_el is None:
            continue
        arxiv_id = (id_el.text or "").strip()
        # Convert http://arxiv.org/abs/XXXX to abs URL
        url = arxiv_id if arxiv_id.startswith("http") else f"https://arxiv.org/abs/{arxiv_id}"
        published_str = (published_el.text or "").strip() if published_el is not None else ""
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.now(timezone.utc)
        items.append(RawItem(
            title=(title_el.text or "").strip().replace("\n", " "),
            url=url,
            source="arxiv",
            published_at=published_at,
            content=(summary_el.text or "").strip() if summary_el is not None else "",
        ))
    return items
