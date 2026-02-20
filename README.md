# AI-News-Monitor

面向 AI 专家 / 工程师 / 投资者的技术情报流水线。

## 1. 你会得到什么
- 每次运行自动抓取 AI 信息源（RSS + GitHub）。
- 通过 LLM 或 heuristic 做筛选与打分。
- 输出中文可读日报（JSON / Markdown / HTML）和 Agent 报告。
- 产出完整 Trace，能看到 Scout / Analyst / Critic 每一步。

## 2. 快速启动
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
```

无 API（稳定低成本）：
```powershell
python .\phase1_rss\main.py --no-llm --top-k 10
```

自动选择 LLM（OpenAI/Gemini）：
```powershell
python .\phase1_rss\main.py --top-k 10
```

一键全流程：
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 10 -SkipSync
```

## 3. 关键目录
- `phase1_rss/`: 抓取、筛选、打分、输出
- `phase2_agent/`: 深度分析与行动建议
- `scripts/`: 一键运行、渲染、同步、发布脚本
- `outputs/`: 运行结果与 trace
- `docs/`: 项目文档

## 4. 输出怎么看
- `outputs/digest_*.json`: 结构化日报（机器读取）
- `outputs/digest_*.md`: 人类可读日报
- `outputs/latest_digest.html`: 前端页面
- `outputs/agent_trace/<run_id>/run.log`: 实时/回放日志

## 5. 配置（本地 `.env`）
文件：`phase1_rss/.env`（不要提交）

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-codex
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

LLM_PROVIDER=auto
LLM_BATCH_SIZE=6
LLM_MAX_RETRIES=2

MIN_RSS_QUOTA=5
MIN_GITHUB_QUOTA=2
MAX_ITEMS_PER_SOURCE=3
```

## 6. 文档导航
- `PROJECT.md`: 产品目标、范围、里程碑
- `docs/ARCHITECTURE.md`: 系统架构与评分逻辑
- `docs/DEVELOPMENT_GUIDE.md`: 运行、调试、发布步骤
