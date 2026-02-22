# DEVELOPMENT GUIDE - AI-News-Monitor

## 1. 本地初始化
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
Copy-Item .\phase1_rss\.env.example .\phase1_rss\.env
```

## 2. 推荐命令
Heuristic：
```powershell
.\scripts\run_all.ps1 -Mode heuristic -TopK 10 -SkipSync
```

Gemini：
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 12 -SkipSync
```

仅跑日报：
```powershell
.\scripts\run_daily.ps1 -Mode llm -TopK 12
```

## 3. 偏好训练与反馈
1. 添加手动喜欢条目：
```powershell
python .\scripts\add_liked_item.py --url "https://example.com/article" --title "Example" --tags "agent,benchmark"
```

2. 导入网页反馈（由页面导出 JSON）：
```powershell
python .\scripts\import_web_feedback.py --input .\anm_feedback_export.json
```

3. 生成偏好画像：
```powershell
python .\scripts\update_preference_profile.py
```

4. 偏好画像文件：
- `feedback/preference_profile.json`
5. 云端收集评估：
- `docs/CLOUD_FEEDBACK_EVALUATION.md`

## 4. 结果检查
- `outputs/digest_*.json` 已生成
- `run_meta.analysis_mode` 合理
- `items[*].preference_score` 与 `personalized_total_score` 存在
- `items[*].why_it_matters` 与 `next_action` 存在
- `site/data/latest.json` 已更新

## 5. 发布流程（半自动）
1. `push/PR -> master` 自动跑 `CI Checks`
2. 手动触发 `Build and Publish Static Site`
3. 发布后本地验收：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\post_publish_check.ps1
```

## 6. 安全提交
1. `.env` 不进 git
```powershell
git check-ignore -v phase1_rss/.env
```

2. 扫描密钥
```powershell
rg -n "AIzaSy|sk-|OPENAI_API_KEY=|GEMINI_API_KEY=" . -g "!outputs/**" -g "!site/**"
```
