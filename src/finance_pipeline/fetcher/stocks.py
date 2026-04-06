"""Stock price fetcher using yfinance."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
import yfinance as yf
from finance_pipeline.models import PricePoint

logger = logging.getLogger(__name__)


def _fetch_price(ticker: str, name: str, currency: str) -> PricePoint | None:
    """Fetch latest price and 1-day change for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = float(info.last_price or 0)
        prev_close = float(info.previous_close or 0)
        if prev_close and prev_close > 0:
            change_pct = round((price - prev_close) / prev_close * 100, 2)
        else:
            change_pct = 0.0
        if price <= 0:
            logger.warning("No price data for %s", ticker)
            return None
        return PricePoint(symbol=ticker, name=name, price=round(price, 2),
                          change_pct=change_pct, currency=currency)
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", ticker, e)
        return None


def fetch_stocks(tickers: list[tuple[str, str, str]]) -> list[PricePoint]:
    """Fetch prices for a list of (ticker, name, currency) tuples."""
    results = []
    for ticker, name, currency in tickers:
        point = _fetch_price(ticker, name, currency)
        if point:
            results.append(point)
    return results
