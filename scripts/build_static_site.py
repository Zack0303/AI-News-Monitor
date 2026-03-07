from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"
TEMPLATES_DIR = ROOT / "scripts" / "templates"
SITE_DIR = ROOT / "site"
TRANSLATION_CACHE_PATH = OUTPUTS_DIR / "en_translation_cache.json"


def extract_date_from_filename(filename: str) -> str:
    try:
        date_part = filename.replace("digest_", "").split("_")[0]
        return datetime.strptime(date_part, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return "unknown-date"


def validate_digest_payload(payload: dict[str, Any], filename: str) -> None:
    required_root = {
        "generated_at": str,
        "total_candidates": int,
        "selected": int,
        "run_meta": dict,
        "items": list,
    }
    for key, expected in required_root.items():
        if key not in payload:
            raise ValueError(f"{filename}: missing required key `{key}`")
        if not isinstance(payload.get(key), expected):
            raise ValueError(f"{filename}: key `{key}` must be {expected.__name__}")

    run_meta = payload.get("run_meta", {})
    required_meta = {"analysis_mode": str, "model": str, "fallback_used": bool}
    for key, expected in required_meta.items():
        if key not in run_meta:
            raise ValueError(f"{filename}: run_meta missing `{key}`")
        if not isinstance(run_meta.get(key), expected):
            raise ValueError(f"{filename}: run_meta `{key}` must be {expected.__name__}")

    for idx, item in enumerate(payload.get("items", []), start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{filename}: items[{idx}] must be object")
        for key in ("id", "title", "link", "source"):
            if not isinstance(item.get(key), str) or not item.get(key):
                raise ValueError(f"{filename}: items[{idx}] invalid `{key}`")


def load_all_digests(outputs_dir: Path) -> list[dict[str, Any]]:
    digests: list[dict[str, Any]] = []
    for idx, json_file in enumerate(sorted(outputs_dir.glob("digest_*.json"), reverse=True)):
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[WARN] Skip invalid json: {json_file.name}")
            continue
        if not isinstance(payload, dict):
            print(f"[WARN] Skip non-object digest: {json_file.name}")
            continue
        if "items" not in payload or not isinstance(payload.get("items"), list):
            print(f"[WARN] Skip digest without list items: {json_file.name}")
            continue
        payload["_filename"] = json_file.name
        payload["_date"] = extract_date_from_filename(json_file.name)
        try:
            validate_digest_payload(payload, filename=json_file.name)
        except ValueError as exc:
            if idx == 0:
                raise
            print(f"[WARN] Skip legacy digest without required schema: {exc}")
            continue
        digests.append(payload)
    return digests


def summarize_history(digests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for d in digests:
        items = [x for x in d.get("items", []) if isinstance(x, dict)]
        source_count: dict[str, int] = {}
        for item in items:
            source = str(item.get("source", "unknown"))
            source_count[source] = source_count.get(source, 0) + 1
        top_source = max(source_count, key=source_count.get) if source_count else "-"
        run_meta = d.get("run_meta", {}) or {}
        rows.append(
            {
                "date": d.get("_date", "unknown"),
                "filename": d.get("_filename", ""),
                "selected": d.get("selected", 0),
                "candidates": d.get("total_candidates", 0),
                "mode": run_meta.get("analysis_mode", "unknown"),
                "model": run_meta.get("model", "-"),
                "top_source": top_source,
            }
        )
    return rows


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\- ]+", "", text.lower(), flags=re.UNICODE).strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:80].strip("-") or "item"


def _item_url(item: dict[str, Any], idx: int) -> str:
    slug = _slugify(f"{idx}-{item.get('title', 'item')}")
    return f"./articles/{slug}.html"


def enrich_items_for_ui(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        score = float(item.get("total_score", 0) or 0)
        personalized_score = float(item.get("personalized_total_score", score) or score)
        tier = str(item.get("output_tier", "primary"))
        category = str(item.get("category", "general"))
        source = str(item.get("source", "unknown"))
        if score >= 80:
            action_hint = item.get("next_action") or "建议今天安排快速评审并决定是否跟进。"
        elif score >= 65:
            action_hint = item.get("next_action") or "建议本周内纳入观察并补充上下文。"
        else:
            action_hint = item.get("next_action") or "建议加入 watchlist，等待更多信号。"
        pref_reasons = item.get("preference_reasons", [])
        pref_text = " | ".join([str(x) for x in pref_reasons[:2]]) if pref_reasons else "no-preference-signal"
        reason = (
            f"{source} / {category}，基础分 {score:.1f}，个性化分 {personalized_score:.1f}，"
            f"{'主线候选' if tier == 'primary' else '回填观察'}。"
        )
        y = dict(item)
        y["action_hint"] = action_hint
        y["importance_reason"] = reason
        y["preference_explain"] = pref_text
        y["detail_url"] = _item_url(y, idx)
        enriched.append(y)
    return enriched


def _sanitize_public_digest(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    run_meta = dict(out.get("run_meta", {}) or {})
    if "fallback_reason" in run_meta:
        run_meta["fallback_reason"] = ""
        run_meta["fallback_reason_public"] = "redacted"
    out["run_meta"] = run_meta
    out.pop("_filename", None)
    out.pop("_date", None)
    return out


def _ensure_templates_exist() -> None:
    expected = [
        TEMPLATES_DIR / "index.html.j2",
        TEMPLATES_DIR / "en_index.html.j2",
        TEMPLATES_DIR / "history.html.j2",
        TEMPLATES_DIR / "detail.html.j2",
        TEMPLATES_DIR / "assets" / "style.css",
        TEMPLATES_DIR / "assets" / "app.js",
    ]
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing template files: {missing}")


def _write_public_digest_files(digests: list[dict[str, Any]], output_dir: Path) -> None:
    for d in digests:
        dst = output_dir / "data" / str(d["_filename"])
        public_payload = _sanitize_public_digest(d)
        dst.write_text(
            json.dumps(public_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    latest_public = _sanitize_public_digest(digests[0])
    (output_dir / "data" / "latest.json").write_text(
        json.dumps(latest_public, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _guess_site_base_url() -> str:
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return ""
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", remote)
    if not m:
        return ""
    owner = m.group("owner")
    repo = m.group("repo")
    return f"https://{owner.lower()}.github.io/{repo}/"


def _write_sitemap(output_dir: Path, items: list[dict[str, Any]], base_url: str) -> None:
    if not base_url:
        return
    urls = [
        base_url,
        f"{base_url}history.html",
        f"{base_url}en/",
    ]
    for item in items:
        detail = str(item.get("detail_url", "")).replace("./", "")
        if detail:
            urls.append(f"{base_url}{detail}")
    entries = "\n".join(
        [
            f"  <url><loc>{u}</loc><changefreq>daily</changefreq></url>"
            for u in sorted(set(urls))
        ]
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    (output_dir / "sitemap.xml").write_text(xml, encoding="utf-8")


def _load_translation_cache() -> dict[str, dict[str, Any]]:
    if not TRANSLATION_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(TRANSLATION_CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_translation_cache(cache: dict[str, dict[str, Any]]) -> None:
    TRANSLATION_CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _translation_cache_key(item: dict[str, Any]) -> str:
    blob = json.dumps(
        {
            "id": item.get("id", ""),
            "title": item.get("title", ""),
            "summary_cn": item.get("summary_cn", ""),
            "why_it_matters": item.get("why_it_matters", ""),
            "next_action": item.get("next_action", ""),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return f"{item.get('id', '')}::{digest}"


def _extract_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("Could not parse JSON object from translation output.")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Translation output JSON is not an object.")
    return parsed


def _extract_openai_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str) and payload.get("output_text"):
        return str(payload["output_text"])
    out = payload.get("output", []) or []
    for block in out:
        for content in block.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text
    raise ValueError("OpenAI translation returned empty content.")



def _sanitize_error_message(message: str) -> str:
    return re.sub(r"(key=)[^&\s]+", r"\1***", message, flags=re.IGNORECASE)
def _translation_prompt(fields: dict[str, str]) -> str:
    return (
        "Translate the following Chinese AI news fields into concise natural English. "
        "Keep product/model names unchanged. Return strict JSON object only with keys: "
        "title_en, summary_en, why_it_matters_en, next_action_en. No markdown.\n\n"
        + json.dumps(fields, ensure_ascii=False)
    )


def _translate_with_openai(fields: dict[str, str], api_key: str, model: str) -> dict[str, str]:
    resp = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": _translation_prompt(fields),
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = _extract_openai_text(resp.json())
    parsed = _extract_json_object(text)
    return {
        "title_en": str(parsed.get("title_en", "")).strip(),
        "summary_en": str(parsed.get("summary_en", "")).strip(),
        "why_it_matters_en": str(parsed.get("why_it_matters_en", "")).strip(),
        "next_action_en": str(parsed.get("next_action_en", "")).strip(),
    }


def _translate_with_gemini(fields: dict[str, str], api_key: str, model: str) -> dict[str, str]:
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": _translation_prompt(fields)}]}],
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
    parsed = _extract_json_object(text)
    return {
        "title_en": str(parsed.get("title_en", "")).strip(),
        "summary_en": str(parsed.get("summary_en", "")).strip(),
        "why_it_matters_en": str(parsed.get("why_it_matters_en", "")).strip(),
        "next_action_en": str(parsed.get("next_action_en", "")).strip(),
    }


def _translate_fields_with_fallback(fields: dict[str, str]) -> tuple[dict[str, str], str, str, str]:
    openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    openai_model = (os.getenv("OPENAI_TRANSLATE_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini").strip()
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    gemini_model = (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip()

    if not openai_key and not gemini_key:
        return {}, "none", "-", "fallback_no_provider"

    attempts: list[tuple[str, str, str]] = []
    if openai_key:
        attempts.append(("openai", openai_key, openai_model))
    if gemini_key:
        attempts.append(("gemini", gemini_key, gemini_model))

    last_error = ""
    for provider, key, model in attempts:
        for retry in range(2):
            try:
                if provider == "openai":
                    translated = _translate_with_openai(fields, api_key=key, model=model)
                else:
                    translated = _translate_with_gemini(fields, api_key=key, model=model)
                return translated, provider, model, "translated"
            except Exception as exc:
                last_error = str(exc)
                if retry == 0:
                    time.sleep(1)
    print(f"[WARN] Translation failed; fallback to source text: {_sanitize_error_message(last_error)}")
    return {}, "none", "-", "fallback_provider_error"


def _apply_translation_fallback(item: dict[str, Any], translated: dict[str, str], status: str) -> dict[str, Any]:
    out = dict(item)
    out["title_en"] = translated.get("title_en") or str(item.get("title", ""))
    out["summary_en"] = translated.get("summary_en") or str(item.get("summary_cn", ""))
    out["why_it_matters_en"] = translated.get("why_it_matters_en") or str(item.get("why_it_matters", ""))
    out["next_action_en"] = translated.get("next_action_en") or str(item.get("next_action", ""))

    if any(not out[k].strip() for k in ("title_en", "summary_en", "why_it_matters_en", "next_action_en")):
        for k, src in (
            ("title_en", "title"),
            ("summary_en", "summary_cn"),
            ("why_it_matters_en", "why_it_matters"),
            ("next_action_en", "next_action"),
        ):
            if not out[k].strip():
                out[k] = str(item.get(src, "")).strip()
        return out | {"translation_status": "fallback_partial"}

    return out | {"translation_status": status}


def build_en_latest_payload(selected_items: list[dict[str, Any]], latest: dict[str, Any]) -> dict[str, Any]:
    cache = _load_translation_cache()
    translated_items: list[dict[str, Any]] = []
    cache_hits = 0
    failed = 0

    for item in selected_items:
        key = _translation_cache_key(item)
        translated = {}
        provider = "none"
        model = "-"
        status = "fallback_no_provider"

        cached = cache.get(key)
        if isinstance(cached, dict):
            translated = {
                "title_en": str(cached.get("title_en", "")),
                "summary_en": str(cached.get("summary_en", "")),
                "why_it_matters_en": str(cached.get("why_it_matters_en", "")),
                "next_action_en": str(cached.get("next_action_en", "")),
            }
            provider = str(cached.get("provider", "none"))
            model = str(cached.get("model", "-"))
            status = "cached"
            cache_hits += 1
        else:
            fields = {
                "title": str(item.get("title", "")),
                "summary_cn": str(item.get("summary_cn", "")),
                "why_it_matters": str(item.get("why_it_matters", "")),
                "next_action": str(item.get("next_action", "")),
            }
            translated, provider, model, status = _translate_fields_with_fallback(fields)
            if status == "translated":
                cache[key] = {
                    **translated,
                    "provider": provider,
                    "model": model,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                }

        item_with_translation = _apply_translation_fallback(item, translated, status)
        item_with_translation["translation_provider"] = provider
        item_with_translation["translation_model"] = model
        translated_items.append(item_with_translation)

        if item_with_translation.get("translation_status", "").startswith("fallback"):
            failed += 1

    _save_translation_cache(cache)
    print(
        f"[INFO] EN translation summary: total={len(selected_items)}, "
        f"cache_hits={cache_hits}, fallback={failed}"
    )

    return {
        "generated_at": latest.get("generated_at", datetime.now(timezone.utc).isoformat()),
        "source_digest": latest.get("_filename", ""),
        "translation_updated_at": datetime.now(timezone.utc).isoformat(),
        "selected": len(translated_items),
        "items": translated_items,
    }


def build_site(top_k: int, output_dir: Path) -> Path:
    _ensure_templates_exist()

    env_path = ROOT / "phase1_rss" / ".env"
    load_dotenv(dotenv_path=env_path)

    digests = load_all_digests(OUTPUTS_DIR)
    if not digests:
        raise RuntimeError("No digest json found in outputs/. Run phase1 first.")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)
    (output_dir / "articles").mkdir(parents=True, exist_ok=True)
    (output_dir / "en").mkdir(parents=True, exist_ok=True)

    _write_public_digest_files(digests, output_dir)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )

    latest = digests[0]
    items = [x for x in latest.get("items", []) if isinstance(x, dict)]
    run_meta = latest.get("run_meta", {}) or {}
    selected_items = sorted(
        items,
        key=lambda x: x.get("personalized_total_score", x.get("total_score", 0)),
        reverse=True,
    )[:top_k]
    selected_items = enrich_items_for_ui(selected_items)

    if not selected_items:
        raise RuntimeError("No items selected for latest digest. Abort static publish.")

    source_mix: dict[str, int] = {}
    for item in selected_items:
        source = str(item.get("source", "unknown"))
        source_mix[source] = source_mix.get(source, 0) + 1

    primary_count = len([x for x in selected_items if x.get("output_tier") == "primary"])
    watchlist_count = len(selected_items) - primary_count
    featured_items = selected_items[:3]
    site_meta = {
        "primary_count": primary_count,
        "watchlist_count": watchlist_count,
        "fallback_used": bool(run_meta.get("fallback_used", False)),
        "analysis_mode": run_meta.get("analysis_mode", "unknown"),
        "model": run_meta.get("model", "-"),
    }

    base_url = _guess_site_base_url()
    index_structured_data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "AI News Monitor Daily Digest",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx,
                "name": str(item.get("title", "")),
                "url": (base_url + str(item.get("detail_url", "")).replace("./", "")) if base_url else str(item.get("detail_url", "")),
            }
            for idx, item in enumerate(selected_items, start=1)
        ],
    }

    index_tpl = env.get_template("index.html.j2")
    index_html = index_tpl.render(
        items=selected_items,
        featured_items=featured_items,
        generated_at=latest.get("generated_at", ""),
        date=latest.get("_date", ""),
        candidates=latest.get("total_candidates", 0),
        selected=latest.get("selected", 0),
        run_meta=run_meta,
        site_meta=site_meta,
        source_mix=source_mix,
        index_structured_data=json.dumps(index_structured_data, ensure_ascii=False),
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    detail_tpl = env.get_template("detail.html.j2")
    for item in selected_items:
        detail_structured_data = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": item.get("title", ""),
            "datePublished": latest.get("generated_at", ""),
            "author": {"@type": "Organization", "name": "AI-News-Monitor"},
            "publisher": {"@type": "Organization", "name": "AI-News-Monitor"},
            "mainEntityOfPage": item.get("link", ""),
            "description": item.get("summary_cn", ""),
        }
        detail_html = detail_tpl.render(
            item=item,
            generated_at=latest.get("generated_at", ""),
            detail_structured_data=json.dumps(detail_structured_data, ensure_ascii=False),
        )
        detail_path = output_dir / str(item.get("detail_url", "")).replace("./", "")
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(detail_html, encoding="utf-8")

    history_rows = summarize_history(digests)
    history_tpl = env.get_template("history.html.j2")
    history_html = history_tpl.render(history=history_rows)
    (output_dir / "history.html").write_text(history_html, encoding="utf-8")

    en_payload = build_en_latest_payload(selected_items, latest)
    (output_dir / "data" / "en_latest.json").write_text(
        json.dumps(en_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    en_items = [x for x in en_payload.get("items", []) if isinstance(x, dict)]
    en_featured = en_items[:3]
    en_index_tpl = env.get_template("en_index.html.j2")
    en_index_html = en_index_tpl.render(
        items=en_items,
        featured_items=en_featured,
        generated_at=en_payload.get("generated_at", ""),
        translation_updated_at=en_payload.get("translation_updated_at", ""),
        date=latest.get("_date", ""),
        candidates=latest.get("total_candidates", 0),
        selected=len(en_items),
        site_meta=site_meta,
    )
    (output_dir / "en" / "index.html").write_text(en_index_html, encoding="utf-8")

    build_info = {
        "built_at": datetime.now().isoformat(),
        "source_digest": str(latest.get("_filename", "")),
        "top_k": top_k,
        "selected_items": len(selected_items),
        "en_items": len(en_items),
    }
    (output_dir / "build_info.txt").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assets_src = TEMPLATES_DIR / "assets"
    shutil.copytree(assets_src, output_dir / "assets", dirs_exist_ok=True)
    _write_sitemap(output_dir, selected_items, base_url=base_url)

    return output_dir


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build AI-News-Monitor static site.")
    p.add_argument("--top-k", type=int, default=12, help="Number of items to show on index page.")
    p.add_argument("--output-dir", type=Path, default=SITE_DIR)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    site_dir = build_site(top_k=args.top_k, output_dir=args.output_dir)
    print(f"[OK] Static site built: {site_dir}")
    print(f"[TIP] Preview: cd {site_dir} && python -m http.server 8080")


if __name__ == "__main__":
    main()

