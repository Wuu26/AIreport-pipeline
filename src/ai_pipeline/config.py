from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# LLM (DeepSeek, OpenAI-compatible)
DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
DEEPSEEK_MODEL: str = "deepseek-chat"
LLM_CONCURRENCY: int = 5          # max parallel LLM calls in filter
SCORE_THRESHOLD: float = 0.75

# Slack
SLACK_WEBHOOK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")

# arXiv
ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV"]
ARXIV_MAX_RESULTS = 15

# RSS sources: (name, url, category_hint)
RSS_SOURCES = [
    ("venturebeat",  "https://venturebeat.com/category/ai/feed/",                   "news"),
    ("the-decoder",  "https://the-decoder.com/feed/",                               "news"),
    ("mit-tech",     "https://www.technologyreview.com/feed/",                       "news"),
    ("techcrunch",   "https://techcrunch.com/category/artificial-intelligence/feed/","news"),
    ("qbitai",       "https://www.qbitai.com/feed",                                  "china"),
    ("36kr",         "https://36kr.com/feed",                                         "china"),
    ("jiqizhixin",   "https://www.jiqizhixin.com/rss",                               "china"),
]

# Coarse filter rules
MIN_UPVOTES_HF = 10         # minimum HuggingFace upvotes to pass coarse filter
MAX_AGE_HOURS = 36          # only items published within this window
KEYWORD_BLACKLIST = [
    "sponsored", "advertisement", "partner content",
    "课程报名", "招生", "打折", "限时优惠",
]


def validate_config() -> None:
    """Raise ValueError if required secrets are missing."""
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")
    if not SLACK_WEBHOOK_URL:
        missing.append("SLACK_WEBHOOK_URL")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
