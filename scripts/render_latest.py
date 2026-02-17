from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def find_latest_digest_json(outputs_dir: Path) -> Path:
    candidates = sorted(outputs_dir.glob("digest_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No digest json found in: {outputs_dir}")
    return candidates[-1]


def render_html(payload: dict) -> str:
    generated_at = payload.get("generated_at", "")
    total_candidates = payload.get("total_candidates", 0)
    selected = payload.get("selected", 0)
    items = payload.get("items", [])
    run_meta = payload.get("run_meta", {}) or {}
    mode = run_meta.get("analysis_mode", "unknown")
    model = run_meta.get("model", "-")
    fallback_used = bool(run_meta.get("fallback_used", False))

    source_mix: dict[str, int] = {}
    for item in items:
        source = item.get("source", "unknown")
        source_mix[source] = source_mix.get(source, 0) + 1
    source_mix_text = " | ".join(f"{k}: {v}" for k, v in sorted(source_mix.items()))

    cards = []
    for idx, item in enumerate(items, start=1):
        tier = item.get("output_tier", "primary")
        tier_badge = "PRIMARY" if tier == "primary" else "WATCHLIST"
        cards.append(
            f"""
            <article class="card {tier}">
              <h3>{idx}. {item.get("title", "Untitled")}</h3>
              <p class="meta">
                <span>Source: {item.get("source", "-")}</span>
                <span>Score: {item.get("total_score", 0)}</span>
                <span>Category: {item.get("category", "-")}</span>
                <span class="badge">{tier_badge}</span>
              </p>
              <p class="summary">{item.get("summary_cn", "")}</p>
              <p><a href="{item.get("link", "#")}" target="_blank" rel="noopener noreferrer">Open Link</a></p>
            </article>
            """
        )

    body = "\n".join(cards) if cards else "<p>No relevant items today.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>AI News Monitor Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #070b16;
      --card: #11182c;
      --text: #eaf1ff;
      --muted: #97a9d6;
      --accent: #00d2a8;
      --warning: #ffc857;
      --border: #24345f;
    }}
    body {{
      margin: 0;
      padding: 28px;
      font-family: "IBM Plex Sans", Arial, sans-serif;
      background:
        radial-gradient(1200px 500px at 5% -10%, #1d325f, transparent 60%),
        radial-gradient(1000px 400px at 95% 0%, #123537, transparent 50%),
        var(--bg);
      color: var(--text);
    }}
    .wrap {{
      max-width: 1080px;
      margin: 0 auto;
    }}
    .header {{
      padding: 18px 22px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: rgba(17, 24, 44, 0.88);
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-family: "Space Grotesk", sans-serif;
      letter-spacing: 0.2px;
    }}
    .stats {{
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 14px;
    }}
    .mode {{
      display: inline-block;
      margin-top: 8px;
      font-size: 12px;
      color: #07131f;
      background: var(--accent);
      font-weight: 700;
      border-radius: 999px;
      padding: 4px 10px;
    }}
    .mode.warn {{
      background: var(--warning);
    }}
    .source-mix {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
    .card {{
      border: 1px solid var(--border);
      border-radius: 14px;
      background: rgba(17, 24, 44, 0.92);
      padding: 16px 20px;
      margin-bottom: 12px;
    }}
    .card.watchlist {{
      border-color: #4f5f8f;
      opacity: 0.92;
    }}
    .card h3 {{ margin: 0 0 8px 0; }}
    .meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .badge {{
      color: #091528;
      background: #7bdcff;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      letter-spacing: 0.5px;
    }}
    .summary {{ line-height: 1.5; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="header">
      <h1>AI News Monitor - Daily Digest</h1>
      <div class="stats">
        <span>Generated: {generated_at}</span>
        <span>Candidates: {total_candidates}</span>
        <span>Selected: {selected}</span>
      </div>
      <div class="mode {'warn' if fallback_used else ''}">
        MODE: {mode} | MODEL: {model} | FALLBACK: {str(fallback_used).lower()}
      </div>
      <div class="source-mix">Source Mix: {source_mix_text or '-'}</div>
    </section>
    {body}
    <p style="color: var(--muted); font-size: 12px;">Rendered at {datetime.now().isoformat()}</p>
  </div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render latest digest json to readable HTML.")
    parser.add_argument("--input", help="Path to digest json. Default: latest in outputs")
    parser.add_argument(
        "--output",
        help="Path to html output. Default: outputs/latest_digest.html",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    outputs_dir = project_root / "outputs"
    input_path = Path(args.input) if args.input else find_latest_digest_json(outputs_dir)
    output_path = Path(args.output) if args.output else outputs_dir / "latest_digest.html"

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    html = render_html(payload)
    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] HTML rendered: {output_path}")


if __name__ == "__main__":
    main()
