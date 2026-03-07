# DEVELOPMENT GUIDE - AI-News-Monitor

## 1. 本地初始化
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\phase1_rss\requirements.txt
python -m pip install -r .\phase2_agent\requirements.txt
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

构建中英文站点：
```powershell
python .\scripts\build_static_site.py --top-k 12
```

## 3. 英文版（V1）翻译说明
- 路径：`/en/index.html`（仅 latest）
- 数据：`site/data/en_latest.json`
- 缓存：`outputs/en_translation_cache.json`（按 `item id + 内容 hash`）
- 提供方优先级：OpenAI -> Gemini -> 源文回退
- 翻译失败不阻断中文页面构建

环境变量：
- 必选其一：`OPENAI_API_KEY` 或 `GEMINI_API_KEY`
- 可选：
  - `OPENAI_TRANSLATE_MODEL`（默认 `gpt-4.1-mini`）
  - `OPENAI_MODEL`
  - `GEMINI_MODEL`（默认 `gemini-2.0-flash`）

## 4. 偏好训练与反馈
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

## 5. 结果检查（含英文抽检）
- `outputs/digest_*.json` 已生成
- `site/index.html` 与 `site/en/index.html` 均存在
- `site/data/latest.json` 与 `site/data/en_latest.json` 均存在
- 抽检 Top 3 英文卡片：
  - `title_en` 语义正确
  - `next_action_en` 可执行
  - 模型/产品名未误译
- 检查 `translation_status`：允许少量 `fallback_*`，不应全部 fallback

## 6. 发布流程（半自动）
1. `push/PR -> master` 自动跑 `CI Checks`
2. 手动触发 `Build and Publish Static Site`，可选传 `target_sha`
3. 发布后本地验收：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\post_publish_check.ps1
```

## 7. 安全提交
1. `.env` 不进 git
```powershell
git check-ignore -v phase1_rss/.env
```

2. 扫描密钥
```powershell
rg -n "AIzaSy|sk-|OPENAI_API_KEY=|GEMINI_API_KEY=" . -g "!outputs/**" -g "!site/**"
```
