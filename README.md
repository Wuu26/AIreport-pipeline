# AIreport-pipeline

自动化每日 AI 资讯报告 + 金融市场报告，通过 GitHub Actions 定时运行，结果推送到 Slack。

---

## 功能概览

### AI领域简报（`ai_pipeline`）

每天 **09:00 北京时间** 自动运行，抓取当日最重要的 AI 资讯发送到 Slack `#帮助-ai报告`。

**数据来源：**
- 学术论文：arXiv API、HuggingFace Papers
- 英文媒体：VentureBeat、The Decoder、MIT Tech Review、TechCrunch
- 中文媒体：量子位、机器之心、36氪
- 兜底：DuckDuckGo 网络搜索

**处理流程：**
```
抓取(并行) → 规则粗筛 → DeepSeek 精筛评分 → 生成报告 → 发送 Slack
```

---

### 金融市场简报（`finance_pipeline`）

每个工作日两次自动运行，发送到 Slack `#财经报告`。

| 报告 | 时间 | 内容 |
|------|------|------|
| **早报** | 08:00 北京时间 | 隔夜美股收盘、加密货币、自选股、财经新闻、今日 A 股展望 |
| **晚报** | 21:30 北京时间 | A 股/港股收盘、美股期货、自选股、财经新闻、今晚美股展望 |

**跟踪标的：**
- 指数：S&P 500、纳斯达克、道琼斯、上证、深证、创业板、恒生
- 自选股：英伟达、特斯拉、阿里巴巴、腾讯、中芯国际
- 加密货币：BTC、ETH
- 期货：标普期货、纳指期货（晚报）

**数据来源：** Yahoo Finance（yfinance）、CoinGecko API（免费，无需 Key）、Reuters/CNBC/东方财富 RSS

> WARNING： 报告仅供参考，不构成投资建议。行情数据有 15 分钟延迟。

---

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone https://github.com/Wuu26/AIreport-pipeline.git
cd AIreport-pipeline
pip install -e .
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入以下内容：
```

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...       # AI 报告频道
SLACK_FINANCE_WEBHOOK_URL=https://hooks.slack.com/services/... # 金融报告频道
```

**获取 API Key：**
- DeepSeek：[platform.deepseek.com](https://platform.deepseek.com)
- Slack Webhook：Slack App 管理页 → Incoming Webhooks

### 3. 本地运行

```bash
# AI 每日简报
python -m ai_pipeline.pipeline

# 金融早报
python -m finance_pipeline --mode morning

# 金融晚报
python -m finance_pipeline --mode evening
```

---

## GitHub Actions 自动化部署

### 配置 Secrets

在 GitHub repo → **Settings → Secrets and variables → Actions** 中添加：

| Secret | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `SLACK_WEBHOOK_URL` | AI 报告的 Slack Webhook URL |
| `SLACK_FINANCE_WEBHOOK_URL` | 金融报告的 Slack Webhook URL |

### 运行时间表

| Workflow | 触发时间 | 说明 |
|----------|----------|------|
| `daily_report.yml` | 每天 09:00 北京时间 | AI 每日简报 |
| `finance_report.yml` | 工作日 08:00 北京时间 | 金融早报 |
| `finance_report.yml` | 工作日 21:30 北京时间 | 金融晚报 |

支持在 GitHub Actions 页面手动触发（`workflow_dispatch`）。

---

## 项目结构

```
src/
├── ai_pipeline/          # AI 资讯报告
│   ├── fetcher/          # arXiv、HuggingFace、RSS、WebSearch
│   ├── filter/           # 规则粗筛 + DeepSeek 精筛
│   ├── generator/        # 报告生成
│   └── sender/           # Slack 发送
└── finance_pipeline/     # 金融市场报告
    ├── fetcher/          # yfinance、CoinGecko、RSS 新闻
    ├── analyzer/         # DeepSeek 市场分析
    ├── config.py         # 自选股、数据源配置
    └── pipeline.py       # 主编排器

.github/workflows/
├── daily_report.yml      # AI 报告 cron
└── finance_report.yml    # 金融报告 cron（早报 + 晚报）
```

---

## 运行成本估算

| 项目 | 费用 |
|------|------|
| DeepSeek API（AI 报告）| < $0.02/次 |
| DeepSeek API（金融报告，早报+晚报）| < $0.02/天 |
| yfinance、CoinGecko、RSS | 免费 |
| GitHub Actions | 免费额度内 |

**每月总费用 < $2。**

---

## 运行测试

```bash
python -m pytest tests/ -v
```
