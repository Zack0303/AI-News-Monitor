# AI-News-Monitor

English | [简体中文](./README.zh-CN.md)

AI-News-Monitor is an AI intelligence pipeline for technical audiences:
ingest -> analyze -> select -> publish.

## Core capabilities
- Ingest candidate items from RSS and GitHub.
- Analyze with Gemini (batch + retry) and fallback to heuristic mode on failure.
- Generate daily outputs in JSON, Markdown, and HTML.
- Learn user preferences from manual likes and in-page feedback events.
- Publish an English V1 page at `/en` with LLM translation and fallback.

## Quick start
```powershell
cd E:\VS_workplace\AI-News-Monitor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\phase1_rss\requirements.txt
python -m pip install -r .\phase2_agent\requirements.txt
Copy-Item .\phase1_rss\.env.example .\phase1_rss\.env
```

Run daily digest (Gemini mode):
```powershell
python .\phase1_rss\main.py --top-k 12 --max-rss-per-source 8 --github-limit 10
```

Build static site (Chinese + English `/en`):
```powershell
python .\scripts\build_static_site.py --top-k 12
```

Run full pipeline:
```powershell
.\scripts\run_all.ps1 -Mode llm -TopK 12 -SkipSync
```

## English translation config (V1)
- Provider priority: OpenAI first, then Gemini.
- Configure at least one key: `OPENAI_API_KEY` or `GEMINI_API_KEY`.
- Optional:
  - `OPENAI_TRANSLATE_MODEL` (default: `gpt-4.1-mini`)
  - `OPENAI_MODEL`
  - `GEMINI_MODEL` (default: `gemini-2.0-flash`)

Artifacts:
- `site/en/index.html`
- `site/data/en_latest.json`
- Translation cache: `outputs/en_translation_cache.json`

## Feedback and preference learning
Add liked item:
```powershell
python .\scripts\add_liked_item.py --url "https://github.com/org/repo" --title "Repo Name" --tags "agent,infra" --note "solid implementation"
```

Update preference profile:
```powershell
python .\scripts\update_preference_profile.py
```

Import exported web feedback:
```powershell
python .\scripts\import_web_feedback.py --input .\anm_feedback_export.json
python .\scripts\update_preference_profile.py
```

## CI and release
- CI runs on push/PR to `master` via `CI Checks`.
- Publishing runs via `publish_site.yml`, validates CI, and publishes the specified `target_sha`.

## Docs
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT_GUIDE.md`
- `docs/FEEDBACK_TRAINING_GUIDE.md`
- `docs/GROWTH_ROADMAP.md`
- `docs/CLOUD_FEEDBACK_EVALUATION.md`
- `PROJECT.md`
