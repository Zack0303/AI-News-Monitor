# AI-News-Monitor Architecture

## 1. Scope
本项目是一个手动触发的 AI 技术情报流水线，目标是每天快速得到“可读 + 可执行”的技术动态摘要，并沉淀到 Obsidian。

当前模式：
- 半自动（Manual Trigger）
- 运行入口：`scripts/run_all.ps1`

---

## 2. End-to-End Pipeline

### 2.1 Trigger Layer
手动触发：
- `scripts/run_all.ps1`
- 或分步运行 `phase1_rss/main.py`、`scripts/render_latest.py`、`phase2_agent/agent.py`

### 2.2 Ingestion Layer
由 `phase1_rss/main.py` 完成抓取：
- RSS sources（OpenAI/HF/PwC/LangChain/Ollama/Together/Cloudflare）
- GitHub Search API（Python + AI 方向）

统一结构后进入候选池：
- `id`
- `source`
- `title`
- `link`
- `content`
- `published_at`
- `origin_type`（`rss` or `github`）

### 2.3 Dedup Layer
按 canonical URL / 标题去重，避免重复条目占据 TopK。

### 2.4 Analysis Layer
优先级：
1. OpenAI LLM（若 `OPENAI_API_KEY` 可用）
2. Gemini LLM（若 `GEMINI_API_KEY` 可用）
3. Heuristic（无可用 LLM 或 LLM 失败时 fallback）

LLM目标输出字段：
- `is_relevant`
- `relevance_score`
- `novelty_score`
- `actionability_score`
- `category`
- `summary_cn`
- `key_points`

综合分：
- `total_score = 0.45*relevance + 0.30*novelty + 0.25*actionability`

### 2.5 Selection Layer (Diversified TopK)
由 `select_diversified_top_items()` 负责：
- 来源配额：`MIN_RSS_QUOTA`、`MIN_GITHUB_QUOTA`
- 单源上限：`MAX_ITEMS_PER_SOURCE`
- 相关条目不足时自动补 `watchlist`，保障输出数量可读。

### 2.6 Output Layer
Phase1 产出：
- `outputs/digest_*.md`（人读日报）
- `outputs/digest_*.json`（机读结构化）
- `outputs/latest_digest.html`（前端看板）

### 2.7 Phase2 Agent Layer
由 `phase2_agent/agent.py` 执行：
- GitHub 项目背调（stars/forks/watchers/活跃度等）
- 非 GitHub 内容价值分层（P0/P1/P2）
- 输出执行队列（Action Queue）

Phase2 产出：
- `outputs/agent_report_*.md`
- `outputs/agent_report_*.json`

### 2.8 Knowledge Sync Layer
由 `scripts/sync_obsidian.ps1` 同步到：
- `90-AI-News-Monitor/Daily`
- `90-AI-News-Monitor/Agent`
- `90-AI-News-Monitor/Data`
- 更新 `90-AI-News-Monitor/LATEST.md`

---

## 3. Run Meta and Traceability
每次 Phase1 运行会记录 `run_meta`（写入 digest json + md）：
- `analysis_mode`（`llm_openai` / `llm_gemini` / `heuristic` / `heuristic_fallback`）
- `model`
- `fallback_used`
- `fallback_reason`
- 参数快照（`top_k`、`max_rss_per_source`、`github_limit`）

用途：
- 追踪“本次结果到底是 LLM 还是规则”
- 排查质量波动原因

---

## 4. Current Filtering Logic

### 4.1 LLM Mode
模型负责语义判定与中文摘要，输出结构化字段。

### 4.2 Heuristic Mode
关键词打分 + 源权重：
- 正向关键词：agent/tool/model/inference/evaluation 等
- 负向关键词：promo/sponsored/discount 等
- Trusted RSS source bonus
- RSS 与 GitHub 阈值不同（RSS稍宽）

### 4.3 Why this design
目标是保证：
- LLM可用时质量高
- LLM不可用时链路不断
- 输出数量和来源分布可控

### 4.4 LLM/LLG Working Method
当前 LLM（OpenAI/Gemini）在本系统中的角色是“推理打分器”，不是“模型本体训练器”：
- 输入：抓取后的候选条目（title/content/source/link）
- 输出：`is_relevant`、三类分数、分类、中文摘要
- 系统再用固定公式和配额策略完成最终排序与选取

一句话：LLM 负责语义判断，系统负责决策规则。

### 4.5 Feedback Loop (评分反馈如何影响后续结果)
可以，而且应该影响。当前系统支持“通过配置和规则改变下一次结果”：
- 调整配额：`MIN_RSS_QUOTA`、`MIN_GITHUB_QUOTA`
- 调整来源权重：trusted source bonus
- 调整关键词词典：正负词表
- 调整输出数量：`top_k`

这属于“策略层反馈闭环”，会在下一次运行中改变结果分布和排序。

---

## 4A. 这是不是 AI 训练？
结论：当前主要是“策略调优 + 推理系统优化”，不是严格意义上的模型训练。

### 4A.1 现在做的是
- Prompt工程
- 规则/阈值调优
- 配额与权重调优
- 数据后处理与重排

这更接近产品工程和机器学习系统调参，不是在更新模型参数。

### 4A.2 真正的“模型训练/微调”通常指
- 使用标注数据进行监督微调（SFT）
- 偏好优化（如 DPO/RLHF）
- 更新模型权重后产生新的模型版本

当前项目未进行这些步骤，因此不属于“训练了一个新模型”。

### 4A.3 未来可升级路径（如果要进入训练）
1. 建立人工标注集（相关/不相关、质量等级）
2. 记录线上判定与人工反馈
3. 用标注数据训练 reranker 或分类器
4. 再接入模型微调流程（按成本和收益评估）

---

## 5. Product-Level Design Decisions
1. 先“可运行”再“全自动”：降低初期失败风险。
2. 多源 + 配额策略：避免单源霸榜，提高信息广度。
3. 双层报告：
- Phase1 给“发生了什么”
- Phase2 给“该做什么”
4. Obsidian 持久化：保证知识沉淀和复盘。

---

## 6. Config Surface
关键配置（`phase1_rss/.env`）：
- LLM: `OPENAI_API_KEY`, `OPENAI_MODEL`, `GEMINI_API_KEY`, `GEMINI_MODEL`
- Selection: `MIN_RSS_QUOTA`, `MIN_GITHUB_QUOTA`, `MAX_ITEMS_PER_SOURCE`
- Optional: `GITHUB_TOKEN`, SMTP 相关

建议默认：
- `TopK=12`
- `MIN_RSS_QUOTA=5`
- `MIN_GITHUB_QUOTA=2`
- `MAX_ITEMS_PER_SOURCE=3`

---

## 7. Common Failure Modes
1. Gemini 429
- 原因：配额/速率限制
- 处理：等待窗口恢复或提额，系统自动 fallback

2. LLM 输出 JSON 解析失败
- 原因：模型输出格式偏离 schema
- 处理：`responseMimeType=application/json` + fallback

3. 某些 RSS 失效
- 原因：源地址变更/站点策略变化
- 处理：定期源健康检查，替换不可用 URL

4. 输出质量波动
- 原因：来源占比失衡、fallback占比升高
- 处理：看 `run_meta` + source mix 调参

---

## 8. How to Run
### Full Pipeline (recommended)
```powershell
cd E:\VS_workplace\AI-News-Monitor
.\scripts\run_all.ps1 -Mode llm -TopK 12 -MaxRssPerSource 10 -GitHubLimit 10 -VaultPath "E:\Career\Career"
```

### Heuristic only
```powershell
.\scripts\run_all.ps1 -Mode heuristic -TopK 12
```

---

## 9. Next Optimization Backlog
1. 增加质量指标面板（LLM成功率、fallback率、来源占比、重复率）
2. 非 GitHub 条目引入正文抽取后再评估
3. 增加 X API 账号流（Notion 创始人/官方）
4. 增加自动重试与告警（进入全自动前）
5. 接入数据库（Supabase）做历史查询和趋势分析
