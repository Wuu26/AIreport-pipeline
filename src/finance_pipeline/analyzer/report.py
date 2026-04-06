"""Finance report generator using DeepSeek."""
from __future__ import annotations
import logging
from datetime import date
from openai import AsyncOpenAI
from finance_pipeline.models import MarketSnapshot, NewsItem
from finance_pipeline.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = {"USD": "$", "HKD": "HK$", "CNY": "¥"}


def _fmt_price(p) -> str:
    sym = CURRENCY_SYMBOLS.get(p.currency, "")
    arrow = "▲" if p.change_pct > 0 else ("▼" if p.change_pct < 0 else "─")
    sign = "+" if p.change_pct > 0 else ""
    return f"{p.name} {p.symbol}　{sym}{p.price:,.2f}　{arrow} {sign}{p.change_pct:.2f}%"


def _format_snapshot(snapshot: MarketSnapshot) -> str:
    lines = []
    if snapshot.indices:
        label = "隔夜美股（收盘）" if snapshot.mode == "morning" else "今日收盘"
        lines.append(f"【{label}】")
        for p in snapshot.indices:
            lines.append(_fmt_price(p))
    if snapshot.futures:
        lines.append("【美股期货（盘前）】")
        for p in snapshot.futures:
            lines.append(_fmt_price(p))
    if snapshot.crypto:
        lines.append("【加密货币】")
        for p in snapshot.crypto:
            lines.append(_fmt_price(p))
    if snapshot.watchlist:
        lines.append("【自选股】")
        for p in snapshot.watchlist:
            lines.append(_fmt_price(p))
    return "\n".join(lines)


def _format_news(news: list[NewsItem]) -> str:
    if not news:
        return "暂无最新财经新闻。"
    return "\n".join(f"- {n.title} [{n.source}] {n.url}" for n in news[:8])


MORNING_PROMPT = """你是一位专业的金融分析师，根据以下市场数据和新闻，生成今日A股盘前简报（Slack markdown格式）。

市场数据：
{market_data}

最新财经新闻：
{news}

今日日期：{today}

生成Slack格式报告（用Slack bold *text*，不用 **text**）：

📊 *金融早报 | {today}*

🌏 *隔夜美股（收盘）*
[各指数，每行：名称 代码　价格　▲/▼ 涨跌幅%]

🪙 *加密货币*
[BTC | ETH 同一行]

📌 *自选股（昨收）*
[每只一行]

📰 *关键财经新闻*
[最多3条重要新闻，每条：*标题* [来源 →](url)，下一行一句话摘要]

🤖 *今日 A 股展望*
[2-4句话，结合隔夜美股走势分析：今日A股关注点、主要风险、潜在机会板块。给出具体判断。]

_以上仅供参考，不构成投资建议。数据：Yahoo Finance · CoinGecko | 15分钟延迟_

规则：无数据区段省略；新闻必须带链接；使用Slack bold *text*。"""

EVENING_PROMPT = """你是一位专业的金融分析师，根据以下市场数据和新闻，生成今晚美股盘前简报（Slack markdown格式）。

市场数据：
{market_data}

最新财经新闻：
{news}

今日日期：{today}

生成Slack格式报告（用Slack bold *text*，不用 **text**）：

📊 *金融晚报 | {today}*

🇨🇳 *A股今日收盘*
[上证、深证、创业板]

🇭🇰 *港股收盘*
[恒生指数]

🌕 *美股期货（盘前）*
[标普期货、纳指期货]

🪙 *加密货币*
[BTC | ETH]

📌 *自选股*
[每只一行]

📰 *关键财经新闻*
[最多3条，每条：*标题* [来源 →](url)，下一行一句话摘要]

🤖 *今晚美股展望*
[2-4句话，结合A股/港股走势+期货分析：今晚美股关注点、催化剂或风险、关键板块。给出具体判断。]

_以上仅供参考，不构成投资建议。数据：Yahoo Finance · CoinGecko | 15分钟延迟_

规则：无数据区段省略；新闻必须带链接；使用Slack bold *text*。"""


async def generate_finance_report(snapshot: MarketSnapshot, news: list[NewsItem]) -> str:
    """Generate Slack markdown finance report using DeepSeek."""
    today = date.today().strftime("%Y-%m-%d")
    market_data = _format_snapshot(snapshot)
    news_text = _format_news(news)
    prompt_template = MORNING_PROMPT if snapshot.mode == "morning" else EVENING_PROMPT
    prompt = prompt_template.format(market_data=market_data, news=news_text, today=today)

    client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    try:
        resp = await client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3,
        )
        report = resp.choices[0].message.content or ""
        logger.info("Finance report generated: %d chars (mode=%s)", len(report), snapshot.mode)
        return report.strip()
    except Exception as e:
        logger.error("Finance report generation failed: %s", e)
        raise
