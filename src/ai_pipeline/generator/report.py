"""Report generator — produces Slack markdown from scored items."""
from __future__ import annotations
import json
import logging
from collections import defaultdict
from datetime import date
from openai import AsyncOpenAI
from ai_pipeline.models import ScoredItem
from ai_pipeline.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

REPORT_TEMPLATE = """You are generating an AI daily briefing for Slack.

Today's date: {today}

Items by category (JSON):
{items_json}

Generate a Slack-formatted markdown report following this EXACT structure.
Use ONLY the items provided — do not invent or add any items.
Each item MUST include its URL as a markdown link.
Sections with no items should be OMITTED entirely.

Format:
```
*🤖 AI 每日简报 | {today}*

---

*📌 今日头条*

*<title>* [→](<url>)
<one sentence description>

---

*📄 学术动态*（HuggingFace · arXiv）

*<paper title>* [arXiv →](<url>) or [HF →](<url>)
<core contribution in one sentence>

---

*🇨🇳 中国 AI 动态*

*<title>* [<source> →](<url>)
<description>

---

*🚀 开源生态*

*<title>* [GitHub →](<url>)
<description>

---

*🌍 行业新闻*

*<title>* [<source> →](<url>)
<description>

---

*💰 融资 & 产品*

*<title>* [<source> →](<url>)
<description>

---
_来源：[arXiv](https://arxiv.org) · [HuggingFace Papers](https://huggingface.co/papers) · [VentureBeat AI](https://venturebeat.com/category/ai) · [The Decoder](https://the-decoder.com) · [MIT Tech Review](https://www.technologyreview.com) · [TechCrunch AI](https://techcrunch.com/category/artificial-intelligence/) · [量子位](https://www.qbitai.com) · [机器之心](https://www.jiqizhixin.com) · [36氪](https://36kr.com) | 生成时间：{today}_
```

Rules:
- "今日头条" contains the top 2 highest scoring items regardless of category (no more than 2)
- Each section has at most 3 items
- Each item is two lines: title+link on line 1, description on line 2, blank line between items
- Use Slack bold syntax: *text* (not **text**)
- Keep descriptions concise (one sentence)
- If a section has no items, omit it entirely
- Quality over quantity: fewer excellent items is better than many mediocre ones
"""


def _items_to_json(items: list[ScoredItem]) -> str:
    """Serialize items to a compact JSON string for the prompt."""
    import json
    data = [
        {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "category": item.category,
            "score": round(item.score, 2),
            "content": item.content[:300],
        }
        for item in items
        if item.category != "skip"
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)


async def generate_report(items: list[ScoredItem]) -> str:
    """Generate Slack markdown report from scored items using DeepSeek."""
    if not items:
        today = date.today().isoformat()
        return f"*🤖 AI 每日简报 | {today}*\n\n_今日暂无高质量内容。_"

    # Cap items: score>=0.85 always included; soft cap 12 total, max 3 per category
    MUST_INCLUDE_THRESHOLD = 0.85
    SOFT_CAP = 12
    MAX_PER_CATEGORY = 3
    items_sorted = sorted(items, key=lambda x: x.score, reverse=True)
    cat_count: dict[str, int] = defaultdict(int)
    capped: list[ScoredItem] = []
    for item in items_sorted:
        if item.category == "skip":
            continue
        must_include = item.score >= MUST_INCLUDE_THRESHOLD
        under_cat_cap = cat_count[item.category] < MAX_PER_CATEGORY
        under_total_cap = len(capped) < SOFT_CAP
        if must_include or (under_cat_cap and under_total_cap):
            capped.append(item)
            cat_count[item.category] += 1
    items = capped

    today = date.today().isoformat()
    items_json = _items_to_json(items)
    prompt = REPORT_TEMPLATE.format(today=today, items_json=items_json)

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    try:
        resp = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.3,
        )
        report = resp.choices[0].message.content or ""
        logger.info("Report generated: %d chars", len(report))
        return report.strip()
    except Exception as e:
        logger.error("Report generation failed: %s", e)
        raise
