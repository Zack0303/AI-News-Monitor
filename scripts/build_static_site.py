from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

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


def load_all_digests(outputs_dir: Path) -> list[dict[str, Any]]:
    digests: list[dict[str, Any]] = []
    for json_file in sorted(outputs_dir.glob("digest_*.json"), reverse=True):
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


def _ensure_templates_exist() -> None:
    expected = [
        TEMPLATES_DIR / "index.html.j2",
        TEMPLATES_DIR / "history.html.j2",
        TEMPLATES_DIR / "assets" / "style.css",
        TEMPLATES_DIR / "assets" / "app.js",
    ]
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing template files: {missing}")


def build_site(top_k: int, output_dir: Path) -> Path:
    _ensure_templates_exist()

    digests = load_all_digests(OUTPUTS_DIR)
    if not digests:
        raise RuntimeError("No digest json found in outputs/. Run phase1 first.")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "assets").mkdir(parents=True, exist_ok=True)

    for d in digests:
        src = OUTPUTS_DIR / str(d["_filename"])
        dst = output_dir / "data" / str(d["_filename"])
        shutil.copy2(src, dst)

    shutil.copy2(OUTPUTS_DIR / str(digests[0]["_filename"]), output_dir / "data" / "latest.json")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html",)),
    )

    latest = digests[0]
    items = [x for x in latest.get("items", []) if isinstance(x, dict)]
    run_meta = latest.get("run_meta", {}) or {}
    selected_items = sorted(items, key=lambda x: x.get("total_score", 0), reverse=True)[:top_k]

    if not selected_items:
        raise RuntimeError("No items selected for latest digest. Abort static publish.")

    source_mix: dict[str, int] = {}
    for item in selected_items:
        source = str(item.get("source", "unknown"))
        source_mix[source] = source_mix.get(source, 0) + 1

    index_tpl = env.get_template("index.html.j2")
    index_html = index_tpl.render(
        items=selected_items,
        generated_at=latest.get("generated_at", ""),
        date=latest.get("_date", ""),
        candidates=latest.get("total_candidates", 0),
        selected=latest.get("selected", 0),
        run_meta=run_meta,
        source_mix=source_mix,
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    history_rows = summarize_history(digests)
    history_tpl = env.get_template("history.html.j2")
    history_html = history_tpl.render(history=history_rows)
    (output_dir / "history.html").write_text(history_html, encoding="utf-8")

    assets_src = TEMPLATES_DIR / "assets"
    shutil.copytree(assets_src, output_dir / "assets", dirs_exist_ok=True)

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
