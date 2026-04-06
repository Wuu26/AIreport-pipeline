"""Finance pipeline configuration."""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

# Slack
SLACK_FINANCE_WEBHOOK_URL: str = os.environ.get("SLACK_FINANCE_WEBHOOK_URL", "")

# LLM (shared DeepSeek)
DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
DEEPSEEK_MODEL: str = "deepseek-chat"

# Watchlist: (ticker, display_name, currency)
WATCHLIST = [
    ("NVDA",      "英伟达",   "USD"),
    ("TSLA",      "特斯拉",   "USD"),
    ("BABA",      "阿里巴巴", "USD"),
    ("0700.HK",   "腾讯",     "HKD"),
    ("688981.SS", "中芯国际", "CNY"),
]

# Indices
INDICES_MORNING = [
    ("^GSPC",  "S&P 500",  "USD"),
    ("^IXIC",  "纳斯达克", "USD"),
    ("^DJI",   "道琼斯",   "USD"),
]
INDICES_EVENING = [
    ("000001.SS", "上证综指", "CNY"),
    ("399001.SZ", "深证成指", "CNY"),
    ("399006.SZ", "创业板指", "CNY"),
    ("^HSI",      "恒生指数", "HKD"),
]

# US Futures (evening only)
FUTURES = [
    ("ES=F", "标普期货", "USD"),
    ("NQ=F", "纳指期货", "USD"),
]

# Crypto (CoinGecko IDs → display name)
CRYPTO_IDS = [
    ("bitcoin",  "BTC"),
    ("ethereum", "ETH"),
]

# Finance news RSS sources: (name, url)
FINANCE_RSS_SOURCES = [
    ("reuters",    "https://feeds.reuters.com/reuters/businessNews"),
    ("cnbc",       "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("eastmoney",  "https://finance.eastmoney.com/rss/news.xml"),
]

# Filter: max age of news in hours
NEWS_MAX_AGE_HOURS = 8


def validate_config() -> None:
    """Raise ValueError if required secrets are missing."""
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY")
    if not SLACK_FINANCE_WEBHOOK_URL:
        missing.append("SLACK_FINANCE_WEBHOOK_URL")
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")
