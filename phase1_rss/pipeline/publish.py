from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
                f"- Why It Matters: {item.get('why_it_matters', '')}",
                f"- Next Action: {item.get('next_action', '')}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path
