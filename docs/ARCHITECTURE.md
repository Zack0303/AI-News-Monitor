# ARCHITECTURE - AI-News-Monitor

## 1. 系统结构
入口：
- `scripts/run_all.ps1`
- `phase1_rss/main.py`

Phase1 执行链路：
1. `ingest` (`phase1_rss/pipeline/ingest.py`)
2. `normalize` (`phase1_rss/pipeline/normalize.py`)
3. `analyze` (`phase1_rss/pipeline/analyze.py`)
4. `select` (`phase1_rss/pipeline/select.py`)
5. `publish` (`phase1_rss/pipeline/publish.py`)

## 2. 分析策略
优先顺序：
1. Gemini（有 key 且未 `--no-llm`）
2. Heuristic fallback

稳定机制：
- `LLM_BATCH_SIZE`
- `LLM_MAX_RETRIES`
- 可重试错误（429/5xx/网络异常/解析失败）

## 3. 排序与个性化
基础评分：
- `total_score = 0.45*relevance + 0.30*novelty + 0.25*actionability`

偏好加权（新增）：
- 从 `feedback/preference_profile.json` 读取权重
- 为每条内容计算 `preference_score`
- 产出 `personalized_total_score`
- 选择阶段按个性化分优先，同时保留来源配额约束

## 4. 反馈学习闭环（新增）
信号来源：
1. 手动喜欢条目：`feedback/liked_items.jsonl`
2. 网页点赞/点踩导入：`feedback/web_feedback.jsonl`

画像生成：
- 脚本：`scripts/update_preference_profile.py`
- 输出：`feedback/preference_profile.json`

网页端：
- 卡片支持 `👍/👎`
- 支持导出反馈 JSON
- 脚本导入：`scripts/import_web_feedback.py`

## 5. 输出与发布
输出：
- `outputs/digest_*.json/.md`
- `site/index.html`, `site/history.html`, `site/data/*.json`

发布：
- CI 自动检查（`ci.yml`）
- Pages 手动发布（`publish_site.yml`，发布前校验 CI 成功）

## 6. 可观测性
`run_meta` 字段：
- `analysis_mode`
- `model`
- `fallback_used`
- `llm_attempts`
- `llm_batch_size`
- `llm_max_retries`

条目级字段（新增）：
- `preference_score`
- `personalized_total_score`
- `preference_reasons`
- `why_it_matters`
- `next_action`

SEO 资产（新增）：
- `site/articles/*.html`（卡片详情页）
- `site/sitemap.xml`
