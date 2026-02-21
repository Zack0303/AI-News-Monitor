# DEVELOPMENT GUIDE - AI-News-Monitor

## 1. 本地初始化
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m pip install -r .\phase1_rss\requirements.txt
Copy-Item .\phase1_rss\.env.example .\phase1_rss\.env
```

## 2. 运行命令
Heuristic（稳定验证）：
```powershell
.\scripts\run_all.ps1 -Mode heuristic -TopK 10 -SkipSync
```

Gemini（失败自动回退 heuristic）：
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 10 -SkipSync
```

仅 Phase1：
```powershell
.\scripts\run_daily.ps1 -Mode llm -TopK 10
```

## 3. 有限 Gemini 配额建议
- `LLM_BATCH_SIZE=4~8`
- `LLM_MAX_RETRIES=1~2`
- `TopK=8~12`

## 4. 半自动发布流程
当前采用半自动：
1. `push/PR -> master` 时，GitHub Actions 自动跑 `CI Checks`（语法、构建、smoke）。
2. Pages 发布仍手动触发 `Build and Publish Static Site` workflow。

这样做的目标是先保证质量门禁，再保留人工发布确认。

## 5. 结果验证清单
- `outputs/digest_*.json` 已生成
- `run_meta.analysis_mode` 符合预期
- `run_meta.fallback_used` 是否为 `true`
- `run_meta.llm_attempts` 是否合理
- `outputs/latest_digest.html` 可正常打开

## 6. 前端渲染
```powershell
python .\scripts\render_latest.py
```
输出：`outputs/latest_digest.html`

## 7. 发布到 GitHub Pages（静态）
```powershell
python .\scripts\build_static_site.py --top-k 12
.\scripts\deploy_static.ps1 -TopK 12
```

## 8. 安全提交（必须）
1. 确认 `.env` 不进 git：
```powershell
git check-ignore -v phase1_rss/.env
```

2. 提交前扫描密钥：
```powershell
rg -n "AIzaSy|sk-|OPENAI_API_KEY=|GEMINI_API_KEY=" . -g "!outputs/**" -g "!site/**"
```

3. 显式提交业务代码与文档：
```powershell
git add phase1_rss scripts docs README.md .github/workflows
git commit -m "update pipeline"
git push origin master
```

