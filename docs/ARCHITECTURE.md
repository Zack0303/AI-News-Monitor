# ARCHITECTURE - AI-News-Monitor

## 1. 系统概览
入口脚本：`scripts/run_all.ps1`  
Phase1 主入口：`phase1_rss/main.py`

Phase1 执行链路：
1. Ingestion：`pipeline/ingest.py` 抓取 RSS + GitHub
2. Normalize：`pipeline/normalize.py` URL/标题去重
3. Analysis：`pipeline/analyze.py` Gemini 或 heuristic
4. Selection：`pipeline/select.py` 配额与排序
5. Publish：`pipeline/publish.py` 输出 digest

## 2. 分析层策略（当前）
优先顺序：
1. Gemini（有 `GEMINI_API_KEY` 且未指定 `--no-llm`）
2. Heuristic fallback

稳定性机制：
- 分批请求：`LLM_BATCH_SIZE`
- 批次重试：`LLM_MAX_RETRIES`
- 可重试错误：429/5xx/网络超时/连接错误/模型输出解析失败

## 3. 评分逻辑
模型输出分：
- `relevance_score`
- `novelty_score`
- `actionability_score`

总分：
- `total_score = 0.45*relevance + 0.30*novelty + 0.25*actionability`

Heuristic 也使用同一总分公式，保证排序口径一致。

## 4. 选择逻辑（约束优化）
函数：`select_diversified_top_items()`
- 总数约束：`top_k`
- 来源配额：`MIN_RSS_QUOTA`, `MIN_GITHUB_QUOTA`
- 单源上限：`MAX_ITEMS_PER_SOURCE`
- 相关内容不足时回填 `watchlist`

## 5. 可观测性（run_meta）
关键字段写入 `digest_*.json -> run_meta`：
- `analysis_mode`：`llm_gemini` / `heuristic` / `heuristic_fallback`
- `model`
- `fallback_used`
- `fallback_reason`（已做 API key 脱敏）
- `llm_provider_attempted`
- `llm_attempts`
- `llm_batch_size`
- `llm_max_retries`

## 6. 关键风险与应对
- Gemini 限流/抖动：batch + retry + heuristic fallback
- RSS 源不稳定：按 source 级别容错，单源失败不中断全局
- 输出质量波动：结合 `run_meta` 与 `source mix` 调整参数

