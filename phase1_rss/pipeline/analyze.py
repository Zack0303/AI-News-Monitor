from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests

from config import NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS, TRUSTED_RSS_SOURCES


def _has_value(name: str) -> bool:
    value = (os.getenv(name) or "").strip()
    if not value:
        return False
    if value.lower() in {"your_key", "changeme", "none"}:
        return False
    return True


def _sanitize_error_message(message: str) -> str:
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


def _safe_score(value: Any) -> int:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0
    return int(max(0, min(100, round(num))))


def _merge_llm_result(
    items: list[dict[str, Any]], arr: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {x["id"]: x for x in arr if isinstance(x, dict) and "id" in x}
    merged: list[dict[str, Any]] = []
    for item in items:
        enrich = by_id.get(item["id"], {})
        relevance = _safe_score(enrich.get("relevance_score", 0))
        novelty = _safe_score(enrich.get("novelty_score", 0))
        actionability = _safe_score(enrich.get("actionability_score", 0))
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
                "why_it_matters": enrich.get("why_it_matters", ""),
                "next_action": enrich.get("next_action", ""),
            }
        )
    return merged


def _gemini_analyze_batch(
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
        "category, summary_cn, key_points(array), "
        "why_it_matters(max 40 Chinese chars), next_action(max 40 Chinese chars). "
        "No markdown, no explanation.\n\n"
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
    return _merge_llm_result(items, arr)


def _chunked(items: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        status_code = exc.response.status_code if exc.response is not None else 0
        return status_code in {408, 409, 429, 500, 502, 503, 504}
    if isinstance(exc, ValueError):
        return True
    return False


def heuristic_analyze(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    analyzed: list[dict[str, Any]] = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('content', '')}".lower()
        positive = sum(1 for k in POSITIVE_KEYWORDS if k in text)
        negative = sum(1 for k in NEGATIVE_KEYWORDS if k in text)
        source_name = str(item.get("source", ""))
        source_bonus = (
            8
            if item.get("origin_type") == "rss" and source_name in TRUSTED_RSS_SOURCES
            else 0
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
                "why_it_matters": (
                    "该条目反映了可落地的技术信号。"
                    if is_relevant
                    else "信息密度较低，暂不优先跟进。"
                ),
                "next_action": (
                    "列入本周跟进并补充原文细节。"
                    if is_relevant
                    else "保留观察，等待更多验证信号。"
                ),
            }
        )
    return analyzed


def analyze_candidates(
    candidates: list[dict[str, Any]],
    use_llm: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    batch_size = max(1, int(os.getenv("LLM_BATCH_SIZE", "6")))
    max_retries = max(0, int(os.getenv("LLM_MAX_RETRIES", "2")))
    gemini_model = _normalize_gemini_model(os.getenv("GEMINI_MODEL"))
    has_gemini = _has_value("GEMINI_API_KEY")

    run_meta = {
        "analysis_mode": "heuristic",
        "model": "heuristic",
        "fallback_used": False,
        "fallback_reason": "",
        "llm_provider_attempted": "none",
        "llm_attempts": 0,
        "llm_batch_size": batch_size,
        "llm_max_retries": max_retries,
    }

    if not use_llm:
        print("[INFO] Running in heuristic mode (--no-llm).")
        return heuristic_analyze(candidates), run_meta

    if not has_gemini:
        print("[WARN] GEMINI_API_KEY missing. Fallback to heuristic.")
        run_meta["analysis_mode"] = "heuristic_fallback"
        run_meta["fallback_used"] = True
        run_meta["fallback_reason"] = "GEMINI_API_KEY missing."
        return heuristic_analyze(candidates), run_meta

    print(f"[INFO] Using Gemini model: {gemini_model}")
    run_meta["analysis_mode"] = "llm_gemini"
    run_meta["model"] = gemini_model
    run_meta["llm_provider_attempted"] = "gemini"

    analyzed: list[dict[str, Any]] = []
    api_key = os.environ["GEMINI_API_KEY"]
    batches = _chunked(candidates, batch_size)
    try:
        for batch_index, batch in enumerate(batches, start=1):
            for retry in range(max_retries + 1):
                try:
                    run_meta["llm_attempts"] += 1
                    batch_result = _gemini_analyze_batch(
                        batch, model=gemini_model, api_key=api_key
                    )
                    analyzed.extend(batch_result)
                    break
                except Exception as exc:
                    can_retry = _is_retryable_exception(exc) and retry < max_retries
                    if can_retry:
                        delay = min(10, 2 ** retry)
                        print(
                            "[WARN] Gemini batch failed, retrying: "
                            f"batch={batch_index}/{len(batches)}, retry={retry + 1}/{max_retries}, delay={delay}s"
                        )
                        time.sleep(delay)
                        continue
                    raise
        return analyzed, run_meta
    except Exception as exc:
        run_meta["analysis_mode"] = "heuristic_fallback"
        run_meta["model"] = "heuristic"
        run_meta["fallback_used"] = True
        run_meta["fallback_reason"] = _sanitize_error_message(str(exc))
        print(
            "[WARN] Gemini analyze failed, fallback to heuristic: "
            f"{run_meta['fallback_reason']}"
        )
        return heuristic_analyze(candidates), run_meta
