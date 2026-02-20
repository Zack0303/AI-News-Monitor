# ARCHITECTURE - AI-News-Monitor

## 1. 系统概览
入口脚本：`scripts/run_all.ps1`

执行链路：
1. Ingestion：抓取 RSS + GitHub
2. Dedup：URL/标题去重
3. Analysis：LLM 或 heuristic 打分
4. Selection：TopK + 配额约束
5. Output：digest / html / agent report / trace

## 2. 分析层策略
优先顺序：
1. OpenAI（有 key）
2. Gemini（有 key）
3. Heuristic fallback

稳定性机制：
- 分批请求（`LLM_BATCH_SIZE`）
- 批次重试（`LLM_MAX_RETRIES`）
- Provider 自动切换（`LLM_PROVIDER=auto`）

## 3. 评分逻辑
模型输出分：
- `relevance_score`
- `novelty_score`
- `actionability_score`

基础分：
- `total_score = 0.45*relevance + 0.30*novelty + 0.25*actionability`

来源加权：
- `weighted_total_score = total_score + source_weight`
- 来源权重来自 `phase1_rss/config.py` 的 `SOURCE_SCORE_WEIGHTS`

最终排序使用 `weighted_total_score`。

## 4. 选择逻辑（约束优化）
函数：`select_diversified_top_items()`
- 总数约束：`top_k`
- 来源配额：`MIN_RSS_QUOTA`, `MIN_GITHUB_QUOTA`
- 单源上限：`MAX_ITEMS_PER_SOURCE`
- 相关内容不足时回填 `watchlist`

## 5. 可观测性
每次运行生成：`outputs/agent_trace/<run_id>/`
- `run.log`
- `01_scout.json`
- `02_analyst.json`
- `03_critic.json`
- `run_meta.json`

关键字段写入 `digest_*.json -> run_meta`：
- `analysis_mode`
- `model`
- `fallback_used`
- `llm_provider_used`
- `trace_dir`

## 6. 关键风险与应对
- LLM 权限/限流失败：自动 fallback
- RSS 源失效：定期校验与替换
- 输出质量波动：看 run_meta + source mix 调参
