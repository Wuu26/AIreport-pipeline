"""Crypto price fetcher using CoinGecko public API (no key required)."""
from __future__ import annotations
import logging
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from finance_pipeline.models import PricePoint

logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def fetch_crypto(
    client: httpx.AsyncClient,
    crypto_ids: list[tuple[str, str]],  # (coingecko_id, display_symbol)
) -> list[PricePoint]:
    """Fetch BTC/ETH prices from CoinGecko."""
    ids = ",".join(cid for cid, _ in crypto_ids)
    try:
        resp = await client.get(
            COINGECKO_URL,
            params={"ids": ids, "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=15,
            headers={"User-Agent": "FinancePipeline/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("CoinGecko fetch failed: %s", e)
        return []

    results = []
    for cid, symbol in crypto_ids:
        item = data.get(cid, {})
        price = item.get("usd", 0)
        change = item.get("usd_24h_change", 0.0)
        if price:
            results.append(PricePoint(
                symbol=symbol,
                name=symbol,
                price=round(float(price), 2),
                change_pct=round(float(change), 2),
                currency="USD",
            ))
    return results
