"""Slack Webhook sender."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import date
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from ai_pipeline.config import SLACK_WEBHOOK_URL

logger = logging.getLogger(__name__)

SLACK_MAX_CHARS = 3900  # Slack block text limit is 3000, message is 4000; use 3900 to be safe
FALLBACK_DIR = Path("logs/fallback")


def _split_message(text: str, limit: int = SLACK_MAX_CHARS) -> list[str]:
    """Split text into chunks at newline boundaries, each within `limit` chars."""
    if len(text) <= limit:
        return [text]
    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def _post_chunk(client: httpx.AsyncClient, chunk: str) -> None:
    """POST a single chunk to Slack Webhook."""
    payload = {"text": chunk}
    resp = await client.post(
        SLACK_WEBHOOK_URL,
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Slack returned {resp.status_code}: {resp.text[:200]}")


def _save_fallback(text: str) -> Path:
    """Save report to fallback file when sending fails."""
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    path = FALLBACK_DIR / f"{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path


async def send_report(report: str) -> bool:
    """
    Send report to Slack. Returns True on success, False on failure.
    On failure, saves to logs/fallback/ and logs the error.
    """
    chunks = _split_message(report)
    async with httpx.AsyncClient() as client:
        try:
            for i, chunk in enumerate(chunks):
                await _post_chunk(client, chunk)
                logger.info("Sent chunk %d/%d (%d chars)", i + 1, len(chunks), len(chunk))
            logger.info("Report sent successfully (%d chunks)", len(chunks))
            return True
        except Exception as e:
            logger.error("Failed to send report after retries: %s", e)
            fallback_path = _save_fallback(report)
            logger.info("Report saved to fallback: %s", fallback_path)
            return False
