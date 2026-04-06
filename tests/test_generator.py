"""Tests for report generator."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from ai_pipeline.models import ScoredItem
from ai_pipeline.generator.report import generate_report, _items_to_json


def make_scored(**kwargs) -> ScoredItem:
    defaults = dict(
        title="Test Paper",
        url="https://arxiv.org/abs/test",
        source="arxiv",
        published_at=datetime.now(timezone.utc),
        content="A test paper.",
        upvotes=0,
        score=0.85,
        reason="Important research",
        category="paper",
    )
    defaults.update(kwargs)
    return ScoredItem(**defaults)


class TestItemsToJson:
    def test_excludes_skip_category(self):
        items = [
            make_scored(category="paper"),
            make_scored(category="skip", url="http://skip.com"),
        ]
        result = _items_to_json(items)
        assert "skip.com" not in result

    def test_truncates_content(self):
        item = make_scored(content="x" * 1000)
        result = _items_to_json([item])
        # Content should be truncated to 300 chars
        assert "x" * 301 not in result

    def test_preserves_chinese_characters(self):
        item = make_scored(title="深度学习新进展", source="qbitai")
        result = _items_to_json([item])
        assert "深度学习新进展" in result


class TestGenerateReport:
    async def test_returns_fallback_for_empty_items(self):
        result = await generate_report([])
        assert "AI 每日简报" in result
        assert "暂无" in result

    async def test_calls_deepseek_with_items(self):
        items = [make_scored()]
        mock_report = "*🤖 AI 每日简报 | 2026-01-15*\n\n*📄 学术动态*\n\n*Test Paper* [arXiv →](https://arxiv.org/abs/test)\nA test paper."

        with patch("ai_pipeline.generator.report.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=type("R", (), {
                    "choices": [type("C", (), {
                        "message": type("M", (), {"content": mock_report})()
                    })()]
                })()
            )
            result = await generate_report(items)

        assert result == mock_report
        mock_client.chat.completions.create.assert_called_once()

    async def test_raises_on_api_error(self):
        items = [make_scored()]
        with patch("ai_pipeline.generator.report.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=RuntimeError("API error")
            )
            with pytest.raises(RuntimeError, match="API error"):
                await generate_report(items)
