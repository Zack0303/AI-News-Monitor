from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from tools import check_github_quality


def find_latest_digest_json(outputs_dir: Path) -> Path:
    files = sorted(outputs_dir.glob("digest_*.json"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No digest json found in {outputs_dir}")
    return files[-1]


def load_digest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Digest payload is not an object.")
    return payload


def _priority_by_score(score: float) -> str:
    if score >= 80:
        return "P0"
    if score >= 65:
        return "P1"
    return "P2"


def run_github_due_diligence(
    items: list[dict[str, Any]], github_token: str | None = None
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    reports: list[dict[str, Any]] = []
    for item in items:
        link = str(item.get("link", "")).strip()
        if "github.com/" not in link:
            continue
        if link in seen:
            continue
        seen.add(link)
        q = check_github_quality(link, github_token=github_token)
        q["from_item_title"] = item.get("title", "")
        q["from_source"] = item.get("source", "")
        q["priority"] = _priority_by_score(float(q.get("quality_score", 0)))
        reports.append(q)
    reports.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    return reports


def run_non_github_analysis(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for item in items:
        link = str(item.get("link", "")).strip()
        if not link or "github.com/" in link:
            continue

        score = float(item.get("total_score", 0) or 0)
        source = str(item.get("source", ""))
        category = str(item.get("category", "general"))
        title = str(item.get("title", "Untitled"))

        source_boost = 0
        if source in {"OpenAI Blog", "Hugging Face Blog", "LangChain Blog"}:
            source_boost = 6
        elif source in {"Together AI Blog", "Cloudflare AI Blog", "Ollama Blog"}:
            source_boost = 4

        final_score = round(min(100.0, score + source_boost), 1)
        priority = _priority_by_score(final_score)
        recommendation = (
            "track-now" if priority == "P0" else "watch-this-week" if priority == "P1" else "archive"
        )

        reports.append(
            {
                "title": title,
                "source": source,
                "link": link,
                "category": category,
                "base_score": score,
                "source_boost": source_boost,
                "insight_score": final_score,
                "priority": priority,
                "recommendation": recommendation,
                "summary_cn": item.get("summary_cn", ""),
            }
        )
    reports.sort(key=lambda x: x.get("insight_score", 0), reverse=True)
    return reports


def _llm_summary_openai(
    payload: dict[str, Any],
    api_key: str,
    model: str = "gpt-5-codex",
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    prompt = (
        "你是AI产品团队的研究负责人。根据输入JSON给出中文执行摘要，要求：\n"
        "1) 今日必须跟进(P0)事项，最多3条；\n"
        "2) 本周观察(P1)事项，最多4条；\n"
        "3) 每条一句行动建议；\n"
        "4) 最后给出一句风险提示。\n"
        "总长度不超过280字。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    resp = client.responses.create(model=model, input=prompt)
    return (getattr(resp, "output_text", "") or "").strip()


def _llm_summary_gemini(
    payload: dict[str, Any],
    api_key: str,
    model: str = "gemini-2.0-flash",
) -> str:
    prompt = (
        "你是AI产品团队的研究负责人。根据输入JSON给出中文执行摘要，要求：\n"
        "1) 今日必须跟进(P0)事项，最多3条；\n"
        "2) 本周观察(P1)事项，最多4条；\n"
        "3) 每条一句行动建议；\n"
        "4) 最后给出一句风险提示。\n"
        "总长度不超过280字。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return (
        ((data.get("candidates") or [{}])[0].get("content") or {})
        .get("parts", [{}])[0]
        .get("text", "")
        .strip()
    )


def synthesize_summary(payload: dict[str, Any], use_llm: bool) -> tuple[str, str, str]:
    if not use_llm:
        return "", "none", "-"

    if os.getenv("OPENAI_API_KEY"):
        model = os.getenv("OPENAI_MODEL", "gpt-5-codex")
        try:
            text = _llm_summary_openai(payload, api_key=os.environ["OPENAI_API_KEY"], model=model)
            return text, "openai", model
        except Exception as exc:
            print(f"[WARN] Agent OpenAI summary failed: {exc}")
            return "", "openai_fallback", model

    if os.getenv("GEMINI_API_KEY"):
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        try:
            text = _llm_summary_gemini(payload, api_key=os.environ["GEMINI_API_KEY"], model=model)
            return text, "gemini", model
        except Exception as exc:
            msg = str(exc)
            msg = msg.replace(os.getenv("GEMINI_API_KEY", ""), "***")
            print(f"[WARN] Agent Gemini summary failed: {msg}")
            return "", "gemini_fallback", model

    return "", "none", "-"


def write_report(
    outputs_dir: Path,
    source_digest: Path,
    digest_meta: dict[str, Any],
    github_reports: list[dict[str, Any]],
    article_reports: list[dict[str, Any]],
    llm_summary: str,
    llm_provider: str,
    llm_model: str,
) -> tuple[Path, Path]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_out = outputs_dir / f"agent_report_{ts}.json"
    md_out = outputs_dir / f"agent_report_{ts}.md"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_digest": str(source_digest),
        "digest_meta": digest_meta,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "github_report_count": len(github_reports),
        "article_report_count": len(article_reports),
        "github_reports": github_reports,
        "article_reports": article_reports,
        "llm_summary": llm_summary or "",
    }
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Agent Intelligence Report",
        "",
        f"- Generated at (UTC): {payload['generated_at']}",
        f"- Source digest: `{source_digest.name}`",
        f"- Digest mode: {digest_meta.get('analysis_mode', '-')}",
        f"- Digest model: {digest_meta.get('model', '-')}",
        f"- Agent LLM provider: {llm_provider}",
        f"- Agent LLM model: {llm_model}",
        f"- GitHub repos analyzed: {len(github_reports)}",
        f"- Non-GitHub articles analyzed: {len(article_reports)}",
        "",
    ]

    if llm_summary:
        lines.extend(["## Executive Summary", llm_summary, ""])

    lines.extend(["## P0 / P1 Action Queue", ""])
    queue = sorted(
        github_reports + article_reports,
        key=lambda x: (x.get("priority", "P9"), -(x.get("quality_score", x.get("insight_score", 0)))),
    )
    for idx, r in enumerate(queue[:10], start=1):
        score = r.get("quality_score", r.get("insight_score", 0))
        title = r.get("from_item_title") or r.get("title") or r.get("repo", "unknown")
        link = r.get("repo_url") or r.get("link", "")
        lines.extend(
            [
                f"{idx}. [{r.get('priority', 'P2')}] {title} ({score})",
                f"   - Recommendation: {r.get('recommendation', '-')}",
                f"   - Link: {link}",
            ]
        )
    lines.append("")

    lines.append("## GitHub Due Diligence")
    lines.append("")
    for idx, r in enumerate(github_reports, start=1):
        lines.extend(
            [
                f"### {idx}. {r.get('owner','?')}/{r.get('repo','?')}",
                f"- Priority: {r.get('priority', 'P2')}",
                f"- Quality Score: {r.get('quality_score', 0)}",
                f"- Recommendation: {r.get('recommendation', 'unknown')}",
                f"- Link: {r.get('repo_url', '')}",
                f"- Signals: Stars={r.get('stars', 0)}, Forks={r.get('forks', 0)}, Watchers={r.get('watchers', 0)}",
                "",
            ]
        )

    lines.append("## Non-GitHub Insights")
    lines.append("")
    for idx, r in enumerate(article_reports, start=1):
        lines.extend(
            [
                f"### {idx}. {r.get('title', 'Untitled')}",
                f"- Priority: {r.get('priority', 'P2')}",
                f"- Insight Score: {r.get('insight_score', 0)}",
                f"- Source: {r.get('source', '-')}",
                f"- Recommendation: {r.get('recommendation', '-')}",
                f"- Link: {r.get('link', '')}",
                "",
            ]
        )

    md_out.write_text("\n".join(lines), encoding="utf-8")
    return md_out, json_out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 2 Agent: unified intelligence report.")
    p.add_argument("--input", help="Path to digest json. Default: latest in outputs/")
    p.add_argument("--use-llm", action="store_true", help="Use LLM to generate executive summary.")
    p.add_argument("--top-n", type=int, default=12, help="Max items per section in report.")
    return p.parse_args()


def main() -> None:
    env_path = Path(__file__).resolve().parents[1] / "phase1_rss" / ".env"
    load_dotenv(dotenv_path=env_path)
    args = parse_args()

    project_root = Path(__file__).resolve().parents[1]
    outputs_dir = project_root / "outputs"
    digest_path = Path(args.input) if args.input else find_latest_digest_json(outputs_dir)

    digest_payload = load_digest(digest_path)
    items = [x for x in digest_payload.get("items", []) if isinstance(x, dict)]
    digest_meta = dict(digest_payload.get("run_meta", {}))

    github_reports = run_github_due_diligence(items, github_token=os.getenv("GITHUB_TOKEN"))[: args.top_n]
    article_reports = run_non_github_analysis(items)[: args.top_n]

    summary_payload = {
        "digest_meta": digest_meta,
        "github_reports": github_reports[:6],
        "article_reports": article_reports[:6],
    }
    llm_summary, llm_provider, llm_model = synthesize_summary(summary_payload, use_llm=args.use_llm)

    md_out, json_out = write_report(
        outputs_dir=outputs_dir,
        source_digest=digest_path,
        digest_meta=digest_meta,
        github_reports=github_reports,
        article_reports=article_reports,
        llm_summary=llm_summary,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    print(f"[OK] Agent report markdown: {md_out}")
    print(f"[OK] Agent report json:     {json_out}")


if __name__ == "__main__":
    main()
