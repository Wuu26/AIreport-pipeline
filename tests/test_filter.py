"""Tests for filter modules."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from ai_pipeline.models import RawItem, ScoredItem
from ai_pipeline.filter.coarse import coarse_filter, _is_too_old, _has_blacklisted_keyword, _fails_upvote_threshold
from ai_pipeline.filter.llm_filter import llm_filter


def make_item(**kwargs) -> RawItem:
    defaults = dict(
        title="Test Item",
        url="http://example.com",
        source="arxiv",
        published_at=datetime.now(timezone.utc),
        content="test content",
        upvotes=0,
    )
    defaults.update(kwargs)
    return RawItem(**defaults)


class TestCoarseFilter:
    def test_passes_recent_clean_item(self):
        item = make_item()
        result = coarse_filter([item])
        assert len(result) == 1

    def test_rejects_old_item(self):
        item = make_item(published_at=datetime.now(timezone.utc) - timedelta(hours=40))
        result = coarse_filter([item])
        assert result == []

    def test_rejects_blacklisted_title(self):
        item = make_item(title="Sponsored content about AI")
        result = coarse_filter([item])
        assert result == []

    def test_rejects_blacklisted_content(self):
        item = make_item(content="This is an advertisement for our course")
        result = coarse_filter([item])
        assert result == []

    def test_rejects_hf_item_low_upvotes(self):
        item = make_item(source="huggingface", upvotes=2)
        result = coarse_filter([item])
        assert result == []

    def test_passes_hf_item_sufficient_upvotes(self):
        item = make_item(source="huggingface", upvotes=10)
        result = coarse_filter([item])
        assert len(result) == 1

    def test_non_hf_item_passes_regardless_of_upvotes(self):
        item = make_item(source="arxiv", upvotes=0)
        result = coarse_filter([item])
        assert len(result) == 1

    def test_empty_input(self):
        assert coarse_filter([]) == []

    def test_is_too_old_exactly_at_threshold(self):
        now = datetime.now(timezone.utc)
        item = make_item(published_at=now - timedelta(hours=36))
        # Exactly 36 hours — should NOT be filtered (> 36, not >= 36)
        assert not _is_too_old(item, now)


class TestLlmFilter:
    async def test_returns_scored_items_above_threshold(self):
        items = [make_item(url=f"http://example.com/{i}") for i in range(3)]
        mock_response = {
            "choices": [{"message": {"content": '{"score": 0.8, "reason": "good", "category": "news"}'}}]
        }
        with patch("ai_pipeline.filter.llm_filter.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=type("R", (), {
                    "choices": [type("C", (), {
                        "message": type("M", (), {"content": '{"score": 0.8, "reason": "good", "category": "news"}'})()
                    })()]
                })()
            )
            result = await llm_filter(items)
        assert len(result) == 3
        assert all(isinstance(r, ScoredItem) for r in result)
        assert all(r.score == 0.8 for r in result)

    async def test_filters_below_threshold(self):
        items = [make_item()]
        with patch("ai_pipeline.filter.llm_filter.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=type("R", (), {
                    "choices": [type("C", (), {
                        "message": type("M", (), {"content": '{"score": 0.3, "reason": "bad", "category": "skip"}'})()
                    })()]
                })()
            )
            result = await llm_filter(items)
        assert result == []

    async def test_handles_llm_parse_error(self):
        items = [make_item()]
        with patch("ai_pipeline.filter.llm_filter.AsyncOpenAI") as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=type("R", (), {
                    "choices": [type("C", (), {
                        "message": type("M", (), {"content": "invalid json {{{{"})()
                    })()]
                })()
            )
            result = await llm_filter(items)
        # Should not raise, just return empty
        assert result == []

    async def test_empty_input(self):
        result = await llm_filter([])
        assert result == []
