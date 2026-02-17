from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import feedparser
import requests
from dotenv import load_dotenv

from config import (
    GITHUB_SEARCH_ENDPOINT,
    NEGATIVE_KEYWORDS,
    POSITIVE_KEYWORDS,
    RSS_SOURCES,
    TRUSTED_RSS_SOURCES,
    github_query_for_recent,
)
from email_sender import render_digest_html, send_digest_email


def _has_value(name: str) -> bool:
    value = (os.getenv(name) or "").strip()
    if not value:
        return False
    if value.lower() in {"your_key", "changeme", "none"}:
        return False
    return True


def _sanitize_error_message(message: str) -> str:
    # Prevent leaking API keys in query strings.
    return re.sub(r"(key=)[^&\s]+", r"\1***", message, flags=re.IGNORECASE)


def _normalize_gemini_model(name: str | None) -> str:
    raw = (name or "").strip()
    if not raw:
        return "gemini-2.0-flash"
    raw_lower = raw.lower().replace(" ", "-")
    aliases = {
        "gemini-1.5-flash": "gemini-1.5-flash",
        "gemini-2.0-flash": "gemini-2.0-flash",
        "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
        "gemini-2.0-flash-lite": "gemini-2.0-flash-lite",
    }
    return aliases.get(raw_lower, raw_lower)


def canonicalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        clean = p._replace(query="", fragment="")
        return urlunparse(clean)
    except Exception:
        return url.strip()


def fetch_rss_items(max_items_per_source: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source in RSS_SOURCES:
        feed = feedparser.parse(source.url)
        for entry in (feed.entries or [])[:max_items_per_source]:
            title = (entry.get("title") or "").strip()
            link = canonicalize_url(entry.get("link", ""))
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            published = (
                entry.get("published")
                or entry.get("updated")
                or datetime.now(timezone.utc).isoformat()
            )
            if not title or not link:
                continue
            items.append(
                {
                    "id": f"rss::{source.name}::{link}",
                    "source": source.name,
                    "title": title,
                    "link": link,
                    "content": summary,
                    "author": entry.get("author", ""),
                    "published_at": str(published),
                    "origin_type": "rss",
                }
            )
    return items


def fetch_github_items(limit: int, token: str | None) -> list[dict[str, Any]]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {
        "q": github_query_for_recent(days=7),
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 50),
        "page": 1,
    }
    resp = requests.get(
        GITHUB_SEARCH_ENDPOINT, params=params, headers=headers, timeout=30
    )
    resp.raise_for_status()
    payload = resp.json()
    items: list[dict[str, Any]] = []
    for repo in payload.get("items", [])[:limit]:
        link = canonicalize_url(repo.get("html_url", ""))
        name = repo.get("full_name", "unknown/repo")
        title = f"{name} (GitHub)"
        desc = repo.get("description") or ""
        stars = int(repo.get("stargazers_count", 0))
        forks = int(repo.get("forks_count", 0))
        pushed_at = repo.get("pushed_at", "")
        content = (
            f"{desc}\nStars: {stars}\nForks: {forks}\n"
            f"Language: {repo.get('language')}\nLast push: {pushed_at}"
        )
        items.append(
            {
                "id": f"github::{name}",
                "source": "GitHub Search",
                "title": title,
                "link": link,
                "content": content,
                "author": (repo.get("owner") or {}).get("login", ""),
                "published_at": pushed_at or datetime.now(timezone.utc).isoformat(),
                "origin_type": "github",
            }
        )
    return items


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = canonicalize_url(item.get("link", "")) or item.get("title", "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _extract_json_array(raw: str) -> list[dict[str, Any]]:
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", raw)
    if not match:
        raise ValueError("Could not parse JSON array from model output.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        raise ValueError("Model output JSON is not a list.")
    return parsed


def llm_analyze_with_codex(
    items: list[dict[str, Any]],
    model: str,
    api_key: str,
) -> list[dict[str, Any]]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    payload = [
        {
            "id": x["id"],
            "title": x["title"],
            "source": x["source"],
            "link": x["link"],
            "content": x["content"][:1800],
        }
        for x in items
    ]
    system_prompt = (
        "You are an AI technology analyst. Return strict JSON array only. "
        "For each input item, output: id, is_relevant(boolean), relevance_score(0-100), "
        "novelty_score(0-100), actionability_score(0-100), category, summary_cn, key_points(array). "
        "If irrelevant, keep scores low and summary_cn concise."
    )
    user_prompt = (
        "Analyze these items and keep output order flexible. "
        "Output JSON array only, no markdown.\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    output_text = getattr(resp, "output_text", None)
    if not output_text:
        output_text = str(resp)
    arr = _extract_json_array(output_text)
    by_id = {x["id"]: x for x in arr if isinstance(x, dict) and "id" in x}
    merged: list[dict[str, Any]] = []
    for item in items:
        enrich = by_id.get(item["id"], {})
        relevance = int(enrich.get("relevance_score", 0) or 0)
        novelty = int(enrich.get("novelty_score", 0) or 0)
        actionability = int(enrich.get("actionability_score", 0) or 0)
        total = round(0.45 * relevance + 0.30 * novelty + 0.25 * actionability, 1)
        merged.append(
            {
                **item,
                "is_relevant": bool(enrich.get("is_relevant", False)),
                "relevance_score": relevance,
                "novelty_score": novelty,
                "actionability_score": actionability,
                "total_score": total,
                "category": enrich.get("category", "general"),
                "summary_cn": enrich.get("summary_cn", ""),
                "key_points": enrich.get("key_points", []),
            }
        )
    return merged


def llm_analyze_with_gemini(
    items: list[dict[str, Any]],
    model: str,
    api_key: str,
) -> list[dict[str, Any]]:
    payload = [
        {
            "id": x["id"],
            "title": x["title"],
            "source": x["source"],
            "link": x["link"],
            "content": x["content"][:1800],
        }
        for x in items
    ]
    prompt = (
        "You are an AI technology analyst. Return strict JSON array only. "
        "For each input item, output fields: id, is_relevant(boolean), "
        "relevance_score(0-100), novelty_score(0-100), actionability_score(0-100), "
        "category, summary_cn, key_points(array). No markdown, no explanation.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    text = (
        ((data.get("candidates") or [{}])[0].get("content") or {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    if not text:
        raise ValueError("Gemini returned empty content.")

    arr = _extract_json_array(text)
    by_id = {x["id"]: x for x in arr if isinstance(x, dict) and "id" in x}
    merged: list[dict[str, Any]] = []
    for item in items:
        enrich = by_id.get(item["id"], {})
        relevance = int(enrich.get("relevance_score", 0) or 0)
        novelty = int(enrich.get("novelty_score", 0) or 0)
        actionability = int(enrich.get("actionability_score", 0) or 0)
        total = round(0.45 * relevance + 0.30 * novelty + 0.25 * actionability, 1)
        merged.append(
            {
                **item,
                "is_relevant": bool(enrich.get("is_relevant", False)),
                "relevance_score": relevance,
                "novelty_score": novelty,
                "actionability_score": actionability,
                "total_score": total,
                "category": enrich.get("category", "general"),
                "summary_cn": enrich.get("summary_cn", ""),
                "key_points": enrich.get("key_points", []),
            }
        )
    return merged


def heuristic_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    analyzed: list[dict[str, Any]] = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('content', '')}".lower()
        positive = sum(1 for k in POSITIVE_KEYWORDS if k in text)
        negative = sum(1 for k in NEGATIVE_KEYWORDS if k in text)
        source_name = str(item.get("source", ""))
        source_bonus = (
            8 if item.get("origin_type") == "rss" and source_name in TRUSTED_RSS_SOURCES else 0
        )
        relevance = max(0, min(100, 25 + positive * 12 - negative * 20 + source_bonus))
        novelty = max(0, min(100, 35 + positive * 9))
        actionability = max(0, min(100, 20 + positive * 8))
        threshold = 48 if item.get("origin_type") == "rss" else 55
        is_relevant = relevance >= threshold
        total = round(0.45 * relevance + 0.30 * novelty + 0.25 * actionability, 1)
        analyzed.append(
            {
                **item,
                "is_relevant": is_relevant,
                "relevance_score": relevance,
                "novelty_score": novelty,
                "actionability_score": actionability,
                "total_score": total,
                "category": "ai-engineering" if is_relevant else "noise",
                "summary_cn": "Heuristic mode summary: keyword-based relevance scoring.",
                "key_points": [],
            }
        )
    return analyzed


def select_diversified_top_items(items: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    relevant = [x for x in items if x.get("is_relevant")]
    relevant.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    if not relevant:
        # No relevant items: backfill from highest-scoring candidates.
        fallback = sorted(items, key=lambda x: x.get("total_score", 0), reverse=True)[:top_k]
        out: list[dict[str, Any]] = []
        for item in fallback:
            y = dict(item)
            y["output_tier"] = "watchlist"
            out.append(y)
        return out

    min_rss = int(os.getenv("MIN_RSS_QUOTA", max(3, top_k // 2)))
    min_github = int(os.getenv("MIN_GITHUB_QUOTA", max(2, top_k // 3)))
    max_per_source = int(os.getenv("MAX_ITEMS_PER_SOURCE", 3))

    min_rss = min(min_rss, top_k)
    min_github = min(min_github, top_k)

    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    source_count: dict[str, int] = {}

    def _try_add(item: dict[str, Any]) -> bool:
        item_id = str(item.get("id", ""))
        source = str(item.get("source", "unknown"))
        if item_id in used_ids:
            return False
        if source_count.get(source, 0) >= max_per_source:
            return False
        selected.append(item)
        used_ids.add(item_id)
        source_count[source] = source_count.get(source, 0) + 1
        return True

    rss_items = [x for x in relevant if x.get("origin_type") == "rss"]
    github_items = [x for x in relevant if x.get("origin_type") == "github"]

    for item in rss_items:
        if len([x for x in selected if x.get("origin_type") == "rss"]) >= min_rss:
            break
        if len(selected) >= top_k:
            break
        _try_add(item)

    for item in github_items:
        if len([x for x in selected if x.get("origin_type") == "github"]) >= min_github:
            break
        if len(selected) >= top_k:
            break
        _try_add(item)

    for item in relevant:
        if len(selected) >= top_k:
            break
        _try_add(item)

    if len(selected) < top_k:
        # Backfill from remaining highest scoring items to keep output volume useful.
        remaining = [
            x
            for x in sorted(items, key=lambda z: z.get("total_score", 0), reverse=True)
            if str(x.get("id", "")) not in used_ids
        ]
        for item in remaining:
            if len(selected) >= top_k:
                break
            y = dict(item)
            y["output_tier"] = "watchlist"
            selected.append(y)
            used_ids.add(str(item.get("id", "")))

    for item in selected:
        item.setdefault("output_tier", "primary" if item.get("is_relevant") else "watchlist")
    return selected


def write_outputs(
    all_items: list[dict[str, Any]],
    top_items: list[dict[str, Any]],
    output_dir: Path,
    run_meta: dict[str, Any],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"digest_{ts}.json"
    md_path = output_dir / f"digest_{ts}.md"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_candidates": len(all_items),
                "selected": len(top_items),
                "run_meta": run_meta,
                "items": top_items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# AI News Monitor Daily Digest",
        "",
        f"- Generated at (UTC): {datetime.now(timezone.utc).isoformat()}",
        f"- Candidates: {len(all_items)}",
        f"- Selected: {len(top_items)}",
        f"- Analysis Mode: {run_meta.get('analysis_mode')}",
        f"- Model: {run_meta.get('model', '-')}",
        f"- Fallback Used: {run_meta.get('fallback_used', False)}",
        "",
    ]
    for idx, item in enumerate(top_items, start=1):
        lines.extend(
            [
                f"## {idx}. {item.get('title')}",
                f"- Source: {item.get('source')}",
                f"- Score: {item.get('total_score')}",
                f"- Category: {item.get('category')}",
                f"- Tier: {item.get('output_tier', 'primary')}",
                f"- Link: {item.get('link')}",
                f"- Summary: {item.get('summary_cn', '')}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 1 RSS + GitHub AI news monitor.")
    p.add_argument("--max-rss-per-source", type=int, default=8)
    p.add_argument("--github-limit", type=int, default=10)
    p.add_argument("--top-k", type=int, default=12)
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("--send-email", action="store_true")
    return p.parse_args()


def main() -> None:
    env_path = Path(__file__).with_name(".env")
    load_dotenv(dotenv_path=env_path)
    args = parse_args()

    root_dir = Path(__file__).resolve().parents[1]
    output_dir = root_dir / "outputs"

    rss_items = fetch_rss_items(args.max_rss_per_source)
    github_items: list[dict[str, Any]] = []
    try:
        github_items = fetch_github_items(
            args.github_limit, token=os.getenv("GITHUB_TOKEN")
        )
    except Exception as exc:
        print(f"[WARN] GitHub fetch failed: {exc}")

    candidates = dedupe_items(rss_items + github_items)
    print(f"[INFO] candidates after dedupe: {len(candidates)}")

    analysis_mode = "heuristic"
    analysis_model = "-"
    fallback_used = False
    fallback_reason = ""

    use_llm = not args.no_llm
    has_openai = _has_value("OPENAI_API_KEY")
    has_gemini = _has_value("GEMINI_API_KEY")
    if use_llm and not (has_openai or has_gemini):
        raise RuntimeError(
            "LLM mode requires OPENAI_API_KEY or GEMINI_API_KEY. "
            "Fill phase1_rss/.env or pass --no-llm."
        )

    if use_llm and has_openai:
        model = os.getenv("OPENAI_MODEL", "gpt-5-codex")
        analysis_mode = "llm_openai"
        analysis_model = model
        print(f"[INFO] Using OpenAI model: {model}")
        try:
            analyzed = llm_analyze_with_codex(
                candidates, model=model, api_key=os.environ["OPENAI_API_KEY"]
            )
        except Exception as exc:
            fallback_used = True
            fallback_reason = _sanitize_error_message(str(exc))
            print(
                "[WARN] OpenAI analyze failed, fallback to heuristic: "
                f"{fallback_reason}"
            )
            analysis_mode = "heuristic_fallback"
            analysis_model = "heuristic"
            analyzed = heuristic_analyze(candidates)
    elif use_llm and has_gemini:
        model = _normalize_gemini_model(os.getenv("GEMINI_MODEL"))
        analysis_mode = "llm_gemini"
        analysis_model = model
        print(f"[INFO] Using Gemini model: {model}")
        try:
            analyzed = llm_analyze_with_gemini(
                candidates, model=model, api_key=os.environ["GEMINI_API_KEY"]
            )
        except Exception as exc:
            fallback_used = True
            fallback_reason = _sanitize_error_message(str(exc))
            print(
                "[WARN] Gemini analyze failed, fallback to heuristic: "
                f"{fallback_reason}"
            )
            analysis_mode = "heuristic_fallback"
            analysis_model = "heuristic"
            analyzed = heuristic_analyze(candidates)
    else:
        print("[INFO] Running in heuristic mode (no LLM key or --no-llm).")
        analysis_mode = "heuristic"
        analysis_model = "heuristic"
        analyzed = heuristic_analyze(candidates)

    top_items = select_diversified_top_items(analyzed, args.top_k)
    by_source: dict[str, int] = {}
    for x in top_items:
        s = str(x.get("source", "unknown"))
        by_source[s] = by_source.get(s, 0) + 1
    print(f"[INFO] selected source mix: {by_source}")

    run_meta = {
        "analysis_mode": analysis_mode,
        "model": analysis_model,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "top_k": args.top_k,
        "max_rss_per_source": args.max_rss_per_source,
        "github_limit": args.github_limit,
    }

    md_path, json_path = write_outputs(analyzed, top_items, output_dir, run_meta=run_meta)
    print(f"[OK] Digest written: {md_path}")
    print(f"[OK] JSON written:   {json_path}")

    if args.send_email:
        required = [
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASS",
            "MAIL_FROM",
            "MAIL_TO",
        ]
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError(f"Missing env vars for email: {missing}")
        html = render_digest_html(top_items, datetime.now(timezone.utc).isoformat())
        send_digest_email(
            smtp_host=os.environ["SMTP_HOST"],
            smtp_port=int(os.environ["SMTP_PORT"]),
            smtp_user=os.environ["SMTP_USER"],
            smtp_password=os.environ["SMTP_PASS"],
            mail_from=os.environ["MAIL_FROM"],
            mail_to=os.environ["MAIL_TO"],
            subject="AI News Monitor - Daily Digest",
            html_body=html,
        )
        print("[OK] Email sent.")


if __name__ == "__main__":
    main()
