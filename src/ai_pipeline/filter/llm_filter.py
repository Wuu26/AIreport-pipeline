"""LLM-based filter using DeepSeek structured output."""
from __future__ import annotations
import asyncio
import json
import logging
from openai import AsyncOpenAI
from ai_pipeline.models import RawItem, FilterResult, ScoredItem
from ai_pipeline.config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    LLM_CONCURRENCY, SCORE_THRESHOLD,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI research curator. Score each item for relevance to an AI daily briefing.

Return a JSON object with these exact fields:
- score: float 0.0-1.0 (relevance score)
- reason: str (one sentence explanation)
- category: one of "paper", "news", "china", "oss", "funding", "skip"

Scoring criteria (be STRICT — default to lower scores, quality over quantity):
- 0.9+: Truly groundbreaking (new flagship model/benchmark from top lab, ≥$100M funding, major policy shift)
- 0.75-0.9: Solid and noteworthy (strong research paper, significant product launch, ≥$50M funding, major open source release)
- 0.6-0.75: Relevant but not exceptional — only score here if clearly worth reading
- below 0.6: Routine updates, incremental work, low-signal content, blog posts without substance

When in doubt, score lower. Most items should score below 0.75.
The threshold is 0.75, so only the top ~25% of content should pass.

Category guide:
- paper: academic papers, research preprints
- news: industry news, product launches, policy
- china: Chinese AI content (any category)
- oss: open source projects, GitHub repos
- funding: investment, acquisitions, fundraising
- skip: spam, ads, irrelevant"""

USER_TEMPLATE = """Title: {title}
Source: {source}
Content: {content}"""


async def _score_item(
    client: AsyncOpenAI,
    item: RawItem,
    semaphore: asyncio.Semaphore,
) -> ScoredItem | None:
    """Score a single item. Returns None on parse failure."""
    async with semaphore:
        try:
            resp = await client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(
                        title=item.title,
                        source=item.source,
                        content=item.content[:500],
                    )},
                ],
                max_tokens=150,
                temperature=0.1,
            )
            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)
            result = FilterResult(
                score=float(data.get("score", 0.0)),
                reason=str(data.get("reason", "")),
                category=data.get("category", "skip"),
            )
            return ScoredItem(**item.model_dump(), **result.model_dump())
        except Exception as e:
            logger.warning("LLM scoring failed for %r: %s", item.title[:60], e)
            return None


async def llm_filter(items: list[RawItem]) -> list[ScoredItem]:
    """Score all items with DeepSeek. Returns items with score >= SCORE_THRESHOLD."""
    if not items:
        return []
    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
    tasks = [_score_item(client, item, semaphore) for item in items]
    results = await asyncio.gather(*tasks)
    scored = [r for r in results if r is not None and r.score >= SCORE_THRESHOLD]
    logger.info("LLM filter: %d → %d items (threshold %.1f)", len(items), len(scored), SCORE_THRESHOLD)
    return scored
