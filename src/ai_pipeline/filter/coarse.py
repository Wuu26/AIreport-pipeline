"""Rule-based coarse filter."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from ai_pipeline.models import RawItem
from ai_pipeline.config import MIN_UPVOTES_HF, MAX_AGE_HOURS, KEYWORD_BLACKLIST

logger = logging.getLogger(__name__)


def coarse_filter(items: list[RawItem]) -> list[RawItem]:
    """Apply rule-based filters. Returns items that pass all rules."""
    passed = []
    now = datetime.now(timezone.utc)
    for item in items:
        if _is_too_old(item, now):
            continue
        if _has_blacklisted_keyword(item):
            continue
        if _fails_upvote_threshold(item):
            continue
        passed.append(item)
    logger.info("Coarse filter: %d → %d items", len(items), len(passed))
    return passed


def _is_too_old(item: RawItem, now: datetime) -> bool:
    """Return True if item is older than MAX_AGE_HOURS."""
    pub = item.published_at
    if pub.tzinfo is None:
        pub = pub.replace(tzinfo=timezone.utc)
    age_hours = (now - pub).total_seconds() / 3600
    return age_hours > MAX_AGE_HOURS


def _has_blacklisted_keyword(item: RawItem) -> bool:
    """Return True if title or content contains a blacklisted keyword."""
    text = (item.title + " " + item.content).lower()
    return any(kw.lower() in text for kw in KEYWORD_BLACKLIST)


def _fails_upvote_threshold(item: RawItem) -> bool:
    """Return True if HuggingFace item has too few upvotes."""
    if item.source == "huggingface" and item.upvotes < MIN_UPVOTES_HF:
        return True
    return False
