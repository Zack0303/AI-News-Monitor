# AI-News-Monitor

AI 技术动态监控系统（Codex Agent 开发版）。

## 目标
- 自动抓取高质量 AI 技术动态（RSS + GitHub，后续可扩展 X）。
- 使用大模型进行语义筛选与结构化总结。
- 每日输出可执行的技术简报（邮件/Slack/飞书）。

## 当前核心信息源
- OpenAI Blog
- Hugging Face Blog
- Papers with Code
- LangChain Blog（Agent 框架/实践）
- Ollama Blog（本地模型与部署）
- Together AI Blog（Agent/eval/infra）
- Cloudflare AI Blog
- GitHub Search（Python + AI）

Notion 创始人爆文建议来源：
- 使用 X API 追踪账号流：`@ivanhzhao`、`@NotionHQ`（Notion 官方博客目前没有稳定 RSS）。

## 开发阶段
1. Phase 1 (MVP): RSS + GitHub 抓取，LLM 筛选，总结推送。
2. Phase 2 (Agent): 使用工具调用做深度背调（代码质量、活跃度、可信度）。

## 目录结构
- `phase1_rss/`：MVP 抓取 + 筛选 + 推送
- `phase2_agent/`：Agent 深度分析
- `.github/workflows/`：定时任务与自动化
- `outputs/`：日报存档
- `docs/`：设计文档

## 运行方式（规划）
- Python 3.10+
- GitHub Actions Cron：每 4 小时抓取一次，08:00 发送日报
- 环境变量管理密钥（禁止硬编码）

## 文档导航（先看这里）
- `README.md`：项目总览 + 快速启动
- `PROJECT.md`：产品蓝图与阶段规划（为什么做）
- `docs/DEVELOPMENT_GUIDE.md`：开发步骤与具体操作（怎么做）
- `docs/ARCHITECTURE.md`：架构与设计记录（演进记录）

## Quick Start
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
python .\phase1_rss\main.py --no-llm --top-k 5
```

Use Codex API mode:
```powershell
$env:OPENAI_API_KEY="your_key"
$env:OPENAI_MODEL="gpt-5-codex"
python .\phase1_rss\main.py --top-k 8
```

Use Gemini API mode:
```powershell
$env:GEMINI_API_KEY="your_key"
$env:GEMINI_MODEL="gemini-2.0-flash"
python .\phase1_rss\main.py --top-k 8
```

Selection policy via `.env`:
```env
MIN_RSS_QUOTA=5
MIN_GITHUB_QUOTA=2
MAX_ITEMS_PER_SOURCE=3
```

## 半自动 vs 全自动
- 半自动（当前先做）：每天手动执行一次脚本，流程固定跑完，不需要定时器。
- 全自动（后续）：用 GitHub Actions/Cron 定时触发，无需人工操作。
- 半自动是否需要 API：
  - 不需要（`heuristic` 模式）
  - 需要（`codex` 模式）

## 一键半自动运行
PowerShell:
```powershell
cd E:\VS_workplace\AI-News-Monitor
.\scripts\run_daily.ps1 -Mode heuristic -TopK 8
```

Codex API 模式:
```powershell
$env:OPENAI_API_KEY="your_key"
$env:OPENAI_MODEL="gpt-5-codex"
.\scripts\run_daily.ps1 -Mode codex -TopK 8
```

CMD (双击或命令行):
```cmd
scripts\run_daily.cmd heuristic
scripts\run_daily.cmd codex
```

## Agent 原型（Phase 2）
运行 GitHub 项目背调原型（基于最新 digest）：
```powershell
python .\phase2_agent\agent.py
```

可选：使用 Codex 生成中文结论总结：
```powershell
$env:OPENAI_API_KEY="your_key"
$env:OPENAI_MODEL="gpt-5-codex"
python .\phase2_agent\agent.py --use-llm
```

## 可视化阅读与 Obsidian 同步

渲染最新 JSON 为前端页面（本地 HTML）：
```powershell
python .\scripts\render_latest.py
```
输出：`outputs/latest_digest.html`

同步到 Obsidian（需提供 Vault 路径）：
```powershell
.\scripts\sync_obsidian.ps1 -VaultPath "E:\ObsidianVault"
```
或先设置环境变量后直接运行：
```powershell
$env:OBSIDIAN_VAULT_PATH="E:\ObsidianVault"
.\scripts\sync_obsidian.ps1
```

## 一键全流程（手动触发）
推荐每天手动执行一次：
```powershell
cd E:\VS_workplace\AI-News-Monitor
.\scripts\run_all.ps1 -Mode llm -TopK 10 -MaxRssPerSource 10 -GitHubLimit 10 -VaultPath "E:\Career\Career"
```

无 API 测试模式：
```powershell
.\scripts\run_all.ps1 -Mode heuristic -TopK 10
```

CMD 包装：
```cmd
scripts\run_all.cmd llm
scripts\run_all.cmd heuristic
```

## Static Site MVP (GitHub Pages)
Build site from `outputs/*.json`:
```powershell
python .\scripts\build_static_site.py --top-k 12
```

Local preview:
```powershell
cd .\site
python -m http.server 8080
```
Open `http://localhost:8080`.

One-click publish helper:
```powershell
.\scripts\deploy_static.ps1 -TopK 12
```

GitHub Actions workflow:
- `.github/workflows/publish_site.yml`
- It builds `site/` and publishes to `gh-pages`.
