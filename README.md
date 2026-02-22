# AI-News-Monitor

面向中文技术受众的 AI 情报流水线（抓取 -> 分析 -> 选择 -> 发布）。

## 1. 核心能力
- 自动抓取 RSS + GitHub 候选内容
- Gemini 分析（批量+重试），失败自动回退 heuristic
- 输出日报（JSON / Markdown / HTML）
- 支持偏好学习：手动喜欢内容 + 页面点赞/点踩反馈

## 2. 快速开始
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
Copy-Item .\phase1_rss\.env.example .\phase1_rss\.env
```

运行日报（Gemini 模式）：
```powershell
python .\phase1_rss\main.py --top-k 12 --max-rss-per-source 8 --github-limit 10
```

一键全流程：
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 12 -SkipSync
```

## 3. 偏好学习（新增）
1. 手动添加你喜欢的内容：
```powershell
python .\scripts\add_liked_item.py --url "https://github.com/org/repo" --title "Repo Name" --tags "agent,infra" --note "做得很扎实"
```

2. 从已有反馈生成画像（每日可跑）：
```powershell
python .\scripts\update_preference_profile.py
```

3. 页面内反馈：
- 卡片支持 `👍 喜欢` / `👎 不喜欢`
- 页面支持导出反馈 JSON（`导出反馈 JSON` 按钮）
- 导入导出的反馈：
```powershell
python .\scripts\import_web_feedback.py --input .\anm_feedback_export.json
python .\scripts\update_preference_profile.py
```

## 4. Phase1 数据流
- `ingest`: 抓取 RSS + GitHub
- `normalize`: 去重
- `analyze`: Gemini/heuristic 打分
- `select`: 配额约束 + 偏好加权重排
- `publish`: 输出 digest

目录：`phase1_rss/pipeline/`

## 5. CI 与发布
- CI：`push/PR -> master` 自动运行 `CI Checks`
- 发布：`publish_site.yml` 手动触发（会校验 CI 通过）

## 6. 文档
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_GUIDE.md`
- `docs/FEEDBACK_TRAINING_GUIDE.md`
- `docs/GROWTH_ROADMAP.md`
- `docs/CLOUD_FEEDBACK_EVALUATION.md`
- `PROJECT.md`
