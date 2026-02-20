# DEVELOPMENT GUIDE - AI-News-Monitor

## 1. 本地运行
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
```

## 2. 推荐运行命令
无 API（稳定验证）：
```powershell
.\scripts\run_all.ps1 -Mode heuristic -TopK 10 -SkipSync
```

有 API（正式模式）：
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 10 -SkipSync
```

## 3. 实时查看日志
运行时在终端可直接看到 `[Scout]/[Analyst]/[Critic]`。

或另开一个终端盯日志：
```powershell
Get-Content .\outputs\agent_trace\<run_id>\run.log -Wait
```

## 4. 结果验证清单
- `outputs/digest_*.json` 已生成
- `run_meta.analysis_mode` 符合预期
- `run_meta.fallback_used` 是否为 `true`
- `outputs/latest_digest.html` 可正常打开

## 5. 前端渲染
```powershell
python .\scripts\render_latest.py
```
输出文件：`outputs/latest_digest.html`

## 6. 发布到 GitHub Pages（静态）
```powershell
python .\scripts\build_static_site.py --top-k 12
.\scripts\deploy_static.ps1 -TopK 12
```

## 7. 安全提交（必须）
1. 确认 `.env` 不进 git：
```powershell
git check-ignore -v phase1_rss/.env
```

2. 提交前扫描密钥：
```powershell
rg -n "AIzaSy|sk-|OPENAI_API_KEY=|GEMINI_API_KEY=" . -g "!outputs/**" -g "!site/**"
```

3. 再提交：
```powershell
git add .
git commit -m "docs: update"
git push origin master
```
