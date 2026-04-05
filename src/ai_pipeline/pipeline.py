"""Main pipeline orchestrator."""
from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import date
from pathlib import Path
from ai_pipeline.config import validate_config
from ai_pipeline.fetcher import fetch_all
from ai_pipeline.filter.coarse import coarse_filter
from ai_pipeline.filter.llm_filter import llm_filter
from ai_pipeline.generator.report import generate_report
from ai_pipeline.sender.slack import send_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

LOG_DIR = Path("logs")


def _save_run_log(log_data: dict) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"{date.today().isoformat()}.json"
    path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def run_pipeline() -> dict:
    """
    Execute the full pipeline. Returns a run log dict.
    Stages: fetch → coarse_filter → llm_filter → generate → send
    Each stage is timed. Slack alert sent on any stage failure.
    """
    validate_config()
    run_log: dict = {"date": date.today().isoformat(), "stages": {}, "success": False}

    # Stage 1: Fetch
    t0 = time.monotonic()
    try:
        raw_items = await fetch_all()
        run_log["stages"]["fetch"] = {
            "items": len(raw_items),
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
        logger.info("Fetch: %d items in %.1fs", len(raw_items), time.monotonic() - t0)
    except Exception as e:
        await _alert(f"Pipeline failed at FETCH: {e}")
        run_log["stages"]["fetch"] = {"error": str(e)}
        _save_run_log(run_log)
        return run_log

    # Stage 2: Coarse filter
    t0 = time.monotonic()
    try:
        coarse_items = coarse_filter(raw_items)
        run_log["stages"]["coarse_filter"] = {
            "items_in": len(raw_items),
            "items_out": len(coarse_items),
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
    except Exception as e:
        await _alert(f"Pipeline failed at COARSE_FILTER: {e}")
        run_log["stages"]["coarse_filter"] = {"error": str(e)}
        _save_run_log(run_log)
        return run_log

    # Stage 3: LLM filter
    t0 = time.monotonic()
    try:
        scored_items = await llm_filter(coarse_items)
        run_log["stages"]["llm_filter"] = {
            "items_in": len(coarse_items),
            "items_out": len(scored_items),
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
    except Exception as e:
        await _alert(f"Pipeline failed at LLM_FILTER: {e}")
        run_log["stages"]["llm_filter"] = {"error": str(e)}
        _save_run_log(run_log)
        return run_log

    # Stage 4: Generate report
    t0 = time.monotonic()
    try:
        report = await generate_report(scored_items)
        run_log["stages"]["generate"] = {
            "chars": len(report),
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
    except Exception as e:
        await _alert(f"Pipeline failed at GENERATE: {e}")
        run_log["stages"]["generate"] = {"error": str(e)}
        _save_run_log(run_log)
        return run_log

    # Stage 5: Send
    t0 = time.monotonic()
    try:
        sent = await send_report(report)
        run_log["stages"]["send"] = {
            "success": sent,
            "elapsed_s": round(time.monotonic() - t0, 2),
        }
    except Exception as e:
        await _alert(f"Pipeline failed at SEND: {e}")
        run_log["stages"]["send"] = {"error": str(e)}
        _save_run_log(run_log)
        return run_log

    run_log["success"] = sent
    log_path = _save_run_log(run_log)
    logger.info("Pipeline complete. Log: %s", log_path)
    return run_log


async def _alert(message: str) -> None:
    """Send a brief failure alert to Slack."""
    try:
        await send_report(f"⚠️ AI Pipeline Alert\n{message}")
    except Exception as e:
        logger.error("Failed to send alert: %s", e)


def main() -> None:
    """Entry point for CLI and GitHub Actions."""
    result = asyncio.run(run_pipeline())
    if not result.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
