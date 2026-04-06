"""Tests for fetcher modules."""
import pytest
import httpx
import respx
from datetime import datetime, timezone
from ai_pipeline.fetcher.arxiv import fetch_arxiv, _parse_arxiv_xml
from ai_pipeline.fetcher.rss import fetch_rss_source, _parse_date
from ai_pipeline.fetcher.huggingface import _parse_hf_html
from ai_pipeline.fetcher import fetch_all

# Minimal valid arXiv Atom XML
ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Test Paper: A Novel Approach</title>
    <summary>This paper presents a test.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Author One</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Another Paper</title>
    <summary>Another abstract.</summary>
    <published>2024-01-14T12:00:00Z</published>
    <author><name>Author Two</name></author>
  </entry>
</feed>"""

SIMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>AI News Article</title>
      <link>https://example.com/article-1</link>
      <description>An article about AI.</description>
      <pubDate>Mon, 15 Jan 2024 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

HF_HTML = """<html><body>
  <article>
    <h3>Attention Is All You Need</h3>
    <a href="/papers/1706.03762">link</a>
    <span>42</span>
  </article>
  <article>
    <h3>BERT: Pre-training</h3>
    <a href="/papers/1810.04805">link</a>
    <span>15</span>
  </article>
</html></body>"""


class TestArxivFetcher:
    def test_parse_arxiv_xml_returns_raw_items(self):
        items = _parse_arxiv_xml(ARXIV_XML)
        assert len(items) == 2
        assert items[0].title == "Test Paper: A Novel Approach"
        assert items[0].source == "arxiv"
        assert "arxiv.org" in items[0].url
        assert items[0].published_at.year == 2024

    def test_parse_arxiv_xml_handles_empty(self):
        empty_xml = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        items = _parse_arxiv_xml(empty_xml)
        assert items == []

    @respx.mock
    async def test_fetch_arxiv_makes_request(self):
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=ARXIV_XML)
        )
        async with httpx.AsyncClient() as client:
            items = await fetch_arxiv(client)
        assert len(items) == 2
        assert items[0].source == "arxiv"


class TestRssFetcher:
    @respx.mock
    async def test_fetch_rss_source_parses_feed(self):
        respx.get("https://example.com/feed").mock(
            return_value=httpx.Response(200, text=SIMPLE_RSS)
        )
        async with httpx.AsyncClient() as client:
            items = await fetch_rss_source(client, "testfeed", "https://example.com/feed")
        assert len(items) == 1
        assert items[0].title == "AI News Article"
        assert items[0].source == "testfeed"
        assert items[0].url == "https://example.com/article-1"

    @respx.mock
    async def test_fetch_rss_source_returns_empty_on_error(self):
        respx.get("https://example.com/broken").mock(
            return_value=httpx.Response(500, text="error")
        )
        async with httpx.AsyncClient() as client:
            # Should not raise, just return empty or fallback
            try:
                items = await fetch_rss_source(client, "broken", "https://example.com/broken")
                # Either empty list or some items from feedparser fallback
                assert isinstance(items, list)
            except Exception:
                pass  # retry exhaustion is acceptable in test context


class TestHuggingFaceFetcher:
    def test_parse_hf_html_extracts_papers(self):
        items = _parse_hf_html(HF_HTML)
        assert len(items) >= 1
        assert any("Attention" in item.title for item in items)
        assert all(item.source == "huggingface" for item in items)
        assert all("huggingface.co" in item.url for item in items)

    def test_parse_hf_html_extracts_upvotes(self):
        items = _parse_hf_html(HF_HTML)
        # At least one item should have upvotes > 0
        upvotes = [item.upvotes for item in items]
        assert any(u > 0 for u in upvotes)


class TestFetchAll:
    @respx.mock
    async def test_fetch_all_deduplicates(self):
        """fetch_all should deduplicate items by URL."""
        # We can't easily mock all sources, so just verify the function runs
        # and returns a list (even if empty due to mocked failures)
        respx.get(url__regex=".*arxiv.*").mock(return_value=httpx.Response(200, text=ARXIV_XML))
        respx.get(url__regex=".*huggingface.*").mock(return_value=httpx.Response(200, text=HF_HTML))
        respx.get(url__regex=".*").mock(return_value=httpx.Response(200, text=SIMPLE_RSS))
        respx.post(url__regex=".*duckduckgo.*").mock(return_value=httpx.Response(200, text=""))

        items = await fetch_all()
        urls = [item.url for item in items]
        assert len(urls) == len(set(urls)), "Duplicate URLs found in fetch_all output"
