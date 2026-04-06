"""Finance pipeline orchestrator."""
from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
import httpx
from finance_pipeline.config import (
    validate_config,
    WATCHLIST, INDICES_MORNING, INDICES_EVENING, FUTURES, CRYPTO_IDS,
    SLACK_FINANCE_WEBHOOK_URL,
)
from finance_pipeline.models import MarketSnapshot
from finance_pipeline.fetcher.stocks import fetch_stocks
from finance_pipeline.fetcher.crypto import fetch_crypto
from finance_pipeline.fetcher.news import fetch_finance_news
from finance_pipeline.analyzer.report import generate_finance_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")


async def _empty() -> list:
    return []


def _save_log(data: dict, mode: str) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"finance-{mode}-{date.today().isoformat()}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def _send_to_slack(report: str) -> bool:
    """POST report to Slack Finance Webhook, split if needed."""
    LIMIT = 3900
    chunks = []
    if len(report) <= LIMIT:
        chunks = [report]
    else:
        current = ""
        for line in report.splitlines(keepends=True):
            if len(current) + len(line) > LIMIT:
                if current:
                    chunks.append(current)
                current = line
            else:
                current += line
        if current:
            chunks.append(current)

    async with httpx.AsyncClient() as client:
        for i, chunk in enumerate(chunks):
            try:
                resp = await client.post(
                    SLACK_FINANCE_WEBHOOK_URL,
                    content=json.dumps({"text": chunk}),
                    headers={"Content-Type": "application/json"},
                    timeout=15,
                )
                if resp.status_code != 200:
                    logger.error("Slack returned %d: %s", resp.status_code, resp.text[:100])
                    return False
                logger.info("Sent chunk %d/%d", i + 1, len(chunks))
            except Exception as e:
                logger.error("Slack send failed: %s", e)
                return False
    return True


async def run(mode: str) -> dict:
    """
    Run the finance pipeline for the given mode ('morning' or 'evening').
    Returns a run log dict with success status.
    """
    validate_config()
    log: dict = {"date": date.today().isoformat(), "mode": mode, "success": False, "stages": {}}

    # Determine which tickers to fetch
    index_tickers = INDICES_MORNING if mode == "morning" else INDICES_EVENING
    future_tickers = [] if mode == "morning" else FUTURES

    # Stage 1: Fetch data in parallel
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            crypto_task = fetch_crypto(client, CRYPTO_IDS)
            news_task = fetch_finance_news(client)
            # stocks is sync — run in executor to not block event loop
            loop = asyncio.get_event_loop()
            indices_task = loop.run_in_executor(None, fetch_stocks, index_tickers)
            watchlist_task = loop.run_in_executor(None, fetch_stocks, WATCHLIST)
            futures_task = (
                loop.run_in_executor(None, fetch_stocks, future_tickers)
                if future_tickers
                else _empty()
            )

            indices, watchlist, futures, crypto, news = await asyncio.gather(
                indices_task, watchlist_task, futures_task, crypto_task, news_task,
                return_exceptions=True,
            )

        # Replace exceptions with empty lists
        def safe(v):
            if isinstance(v, Exception):
                logger.warning("Fetch exception: %s", v)
                return []
            return v or []

        indices, watchlist, futures, crypto, news = map(safe, [indices, watchlist, futures, crypto, news])

        snapshot = MarketSnapshot(
            mode=mode,
            indices=indices,
            futures=futures,
            watchlist=watchlist,
            crypto=crypto,
            timestamp=datetime.now(timezone.utc),
        )
        log["stages"]["fetch"] = {
            "indices": len(indices), "watchlist": len(watchlist),
            "futures": len(futures), "crypto": len(crypto), "news": len(news),
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
        logger.info("Fetch complete: %d indices, %d watchlist, %d crypto, %d news",
                    len(indices), len(watchlist), len(crypto), len(news))
    except Exception as e:
        logger.error("Fetch stage failed: %s", e)
        log["stages"]["fetch"] = {"error": str(e)}
        _save_log(log, mode)
        return log

    # Stage 2: Generate report
    t0 = time.monotonic()
    try:
        report = await generate_finance_report(snapshot, news)
        log["stages"]["generate"] = {"chars": len(report), "elapsed_s": round(time.monotonic() - t0, 2)}
    except Exception as e:
        logger.error("Generate stage failed: %s", e)
        log["stages"]["generate"] = {"error": str(e)}
        _save_log(log, mode)
        return log

    # Stage 3: Send
    t0 = time.monotonic()
    sent = await _send_to_slack(report)
    log["stages"]["send"] = {"success": sent, "elapsed_s": round(time.monotonic() - t0, 2)}
    log["success"] = sent
    _save_log(log, mode)
    logger.info("Finance pipeline complete (mode=%s, success=%s)", mode, sent)
    return log
