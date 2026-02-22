from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"
TEMPLATES_DIR = ROOT / "scripts" / "templates"
SITE_DIR = ROOT / "site"


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
            impact = "High Priority"
            action_hint = item.get("next_action") or "建议今天安排快速评审并决定是否跟进。"
        elif score >= 65:
            impact = "Medium Priority"
            action_hint = item.get("next_action") or "建议本周内纳入观察并补充上下文。"
        else:
            impact = "Watchlist"
            action_hint = item.get("next_action") or "建议加入 watchlist，等待更多信号。"
        pref_reasons = item.get("preference_reasons", [])
        pref_text = " | ".join([str(x) for x in pref_reasons[:2]]) if pref_reasons else "no-preference-signal"
        reason = (
            f"{source} / {category}，基础分 {score:.1f}，个性化分 {personalized_score:.1f}，"
            f"{'主线候选' if tier == 'primary' else '回填观察'}。"
        )
        y = dict(item)
        y["impact_label"] = impact
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
    # Best effort for GitHub Pages path based on git remote.
    try:
        import subprocess

        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return ""
    # Supports https://github.com/<owner>/<repo>.git
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


def build_site(top_k: int, output_dir: Path) -> Path:
    _ensure_templates_exist()

    digests = load_all_digests(OUTPUTS_DIR)
    if not digests:
        raise RuntimeError("No digest json found in outputs/. Run phase1 first.")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)
    (output_dir / "articles").mkdir(parents=True, exist_ok=True)

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

    build_info = {
        "built_at": datetime.now().isoformat(),
        "source_digest": str(latest.get("_filename", "")),
        "top_k": top_k,
        "selected_items": len(selected_items),
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

