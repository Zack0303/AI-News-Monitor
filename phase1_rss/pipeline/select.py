from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_preference_profile() -> dict[str, Any]:
    profile_path = _project_root() / "feedback" / "preference_profile.json"
    if not profile_path.exists():
        return {}
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9\-_]{3,}", text.lower())]


def _domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _apply_preference_scores(
    items: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    source_weights = profile.get("source_weights", {}) or {}
    domain_weights = profile.get("domain_weights", {}) or {}
    keyword_weights = profile.get("keyword_weights", {}) or {}
    alpha = float(os.getenv("PREFERENCE_ALPHA", "1.5"))

    out: list[dict[str, Any]] = []
    for item in items:
        score = 0.0
        reasons: list[str] = []

        source = str(item.get("source", ""))
        if source and source in source_weights:
            delta = float(source_weights[source])
            score += delta
            reasons.append(f"source({source})={delta:+.1f}")

        d = _domain(str(item.get("link", "")))
        if d and d in domain_weights:
            delta = float(domain_weights[d])
            score += delta
            reasons.append(f"domain({d})={delta:+.1f}")

        text = f"{item.get('title', '')} {item.get('summary_cn', '')} {item.get('content', '')}"
        keyword_delta = 0.0
        for token in set(_tokenize(text)):
            if token in keyword_weights:
                keyword_delta += float(keyword_weights[token])
        if keyword_delta:
            score += keyword_delta
            reasons.append(f"keywords={keyword_delta:+.1f}")

        preference_score = round(score, 2)
        base = float(item.get("total_score", 0) or 0)
        personalized = round(base + alpha * preference_score, 2)
        y = dict(item)
        y["preference_score"] = preference_score
        y["personalized_total_score"] = personalized
        y["preference_reasons"] = reasons
        out.append(y)
    return out


def _sort_score(x: dict[str, Any]) -> float:
    return float(x.get("personalized_total_score", x.get("total_score", 0)) or 0)


def select_diversified_top_items(
    items: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    profile = _load_preference_profile()
    scored_items = _apply_preference_scores(items, profile)

    relevant = [x for x in scored_items if x.get("is_relevant")]
    relevant.sort(key=_sort_score, reverse=True)
    if not relevant:
        fallback = sorted(scored_items, key=_sort_score, reverse=True)[:top_k]
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
        remaining = [
            x for x in sorted(scored_items, key=_sort_score, reverse=True) if str(x.get("id", "")) not in used_ids
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

