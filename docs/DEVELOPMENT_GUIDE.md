# AI-News-Monitor 开发步骤与操作手册

本文档是项目的执行入口，目标是让新成员快速理解并运行项目。

## 1. 这个项目做什么
- 每次任务抓取 AI 技术信息源（RSS + GitHub）。
- 对内容做筛选、评分和总结。
- 输出日报文件（Markdown/JSON），后续可邮件推送或接入协作平台。

## 2. 当前范围（Phase 1 MVP）
- 已实现：
  - RSS 抓取
  - GitHub Search 抓取
  - 去重
  - 两种分析模式：
    - `Heuristic`（无 API Key 可跑）
    - `Codex API`（高质量语义筛选）
  - 日报输出到 `outputs/`
- 暂未实现：
  - 完整自动化调度（workflow 需补全）
  - Phase 2 Agent 深度背调

## 3. 代码结构（重点）
- `phase1_rss/main.py`：主流程入口
- `phase1_rss/config.py`：数据源与筛选配置
- `phase1_rss/email_sender.py`：邮件发送模块
- `phase1_rss/.env.example`：环境变量模板
- `outputs/`：每次运行产出的日报

## 4. 开发步骤（建议顺序）
1. 安装依赖
2. 跑 `Heuristic` 模式，验证抓取链路
3. 配置 `OPENAI_API_KEY`，跑 `Codex API` 模式
4. 检查输出质量（Top K 是否合理）
5. 再开启邮件推送

## 5. 本地运行命令
在 PowerShell 中执行：

```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
```

### 5.1 无 API 模式（先验证）
```powershell
python .\phase1_rss\main.py --no-llm --top-k 5
```

### 5.2 Codex API 模式（正式效果）
```powershell
$env:OPENAI_API_KEY="your_key"
$env:OPENAI_MODEL="gpt-5-codex"
python .\phase1_rss\main.py --top-k 8
```

### 5.3 邮件推送（可选）
```powershell
$env:SMTP_HOST="..."
$env:SMTP_PORT="587"
$env:SMTP_USER="..."
$env:SMTP_PASS="..."
$env:MAIL_FROM="..."
$env:MAIL_TO="..."
python .\phase1_rss\main.py --top-k 8 --send-email
```

## 6. 输出文件怎么读
- `outputs/digest_YYYYMMDD_HHMMSS.md`：面向人的日报
- `outputs/digest_YYYYMMDD_HHMMSS.json`：机器可读结果（可接数据库/前端）

关键字段说明：
- `is_relevant`：是否相关
- `relevance_score`：相关性评分
- `novelty_score`：新颖性评分
- `actionability_score`：可执行性评分
- `total_score`：综合排序分
- `summary_cn`：中文摘要

## 7. 验收标准（MVP）
- 命令可稳定执行，不报错退出
- 能生成 `.md + .json` 两份日报
- Top 内容能反映当天有效 AI 技术动态
- 无 API 模式和 API 模式均可运行

## 8. 常见问题
1. 为什么没走 API 模式？
- 未设置 `OPENAI_API_KEY`，会自动退回 `Heuristic`。

2. 为什么推荐条数很少？
- 当前关键词规则较严格，且只保留 `is_relevant=true`。

3. VS Code 没切到项目目录？
- 执行：
```powershell
cd E:\VS_workplace\AI-News-Monitor
code .
```

## 9. 下一步开发任务（建议）
1. 增加更多高质量源（官方博客、研究组织）
2. 完善 GitHub Actions 定时 workflow
3. 增加失败重试和告警
4. 接入 Supabase 做检索和历史统计

## 10. 前端阅读与 Obsidian 同步
### 10.1 生成本地可读前端页面
```powershell
python .\scripts\render_latest.py
```
生成文件：`outputs/latest_digest.html`

### 10.2 同步到 Obsidian
```powershell
.\scripts\sync_obsidian.ps1 -VaultPath "E:\ObsidianVault"
```
可选：先设置环境变量 `OBSIDIAN_VAULT_PATH`，后续直接执行脚本。
