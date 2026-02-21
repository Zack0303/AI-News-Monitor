# AI-News-Monitor

面向 AI 专家 / 工程师 / 投资者的技术情报流水线。

## 1. 你会得到什么
- 自动抓取 AI 信息源（RSS + GitHub）。
- Gemini 分析（分批 + 重试），失败自动回退 heuristic。
- 输出中文日报（JSON / Markdown / HTML）和 Agent 报告。

## 2. 快速启动
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
Copy-Item .\phase1_rss\.env.example .\phase1_rss\.env
```

无 API（稳定低成本）：
```powershell
python .\phase1_rss\main.py --no-llm --top-k 10
```

Gemini 模式（失败自动回退 heuristic）：
```powershell
python .\phase1_rss\main.py --top-k 10
```

一键全流程：
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 10 -SkipSync
```

## 3. Phase1 数据流
- `ingest`：抓取 RSS + GitHub
- `normalize`：URL 规范化 + 去重
- `analyze`：Gemini 打分（batch/retry）或 heuristic
- `select`：TopK + 配额约束 + 回填 watchlist
- `publish`：写出 `digest_*.json/.md`

代码位置：`phase1_rss/pipeline/`

## 4. 输出说明
- `outputs/digest_*.json`：结构化日报
- `outputs/digest_*.md`：可读日报
- `outputs/latest_digest.html`：前端页面
- `run_meta` 关键字段：`analysis_mode`, `model`, `fallback_used`, `fallback_reason`, `llm_attempts`

## 5. 配置（本地 `.env`）
文件：`phase1_rss/.env`（不要提交）

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
LLM_BATCH_SIZE=6
LLM_MAX_RETRIES=2

MIN_RSS_QUOTA=5
MIN_GITHUB_QUOTA=2
MAX_ITEMS_PER_SOURCE=3

GITHUB_TOKEN=
```

## 6. 文档导航
- `PROJECT.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_GUIDE.md`

## 7. CI / 发布
- CI：`push/PR -> master` 自动执行 `CI Checks`（语法、构建、smoke）。
- 发布：`publish_site.yml` 仍为手动触发（半自动发布策略）。
