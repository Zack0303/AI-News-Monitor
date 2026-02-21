from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from email_sender import render_digest_html, send_digest_email
from pipeline.analyze import analyze_candidates
from pipeline.ingest import fetch_github_items, fetch_rss_items
from pipeline.normalize import dedupe_items
from pipeline.publish import write_outputs
from pipeline.select import select_diversified_top_items


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

    print("[PIPELINE] Step 1/5 ingest")
    rss_items = fetch_rss_items(args.max_rss_per_source)
    github_items = []
    try:
        github_items = fetch_github_items(args.github_limit, token=os.getenv("GITHUB_TOKEN"))
    except Exception as exc:
        print(f"[WARN] GitHub fetch failed: {exc}")

    print("[PIPELINE] Step 2/5 normalize+dedupe")
    candidates = dedupe_items(rss_items + github_items)
    print(f"[INFO] candidates after dedupe: {len(candidates)}")

    print("[PIPELINE] Step 3/5 analyze")
    analyzed, analysis_meta = analyze_candidates(candidates, use_llm=not args.no_llm)

    print("[PIPELINE] Step 4/5 select")
    top_items = select_diversified_top_items(analyzed, args.top_k)
    by_source: dict[str, int] = {}
    for x in top_items:
        s = str(x.get("source", "unknown"))
        by_source[s] = by_source.get(s, 0) + 1
    print(f"[INFO] selected source mix: {by_source}")

    run_meta = {
        **analysis_meta,
        "top_k": args.top_k,
        "max_rss_per_source": args.max_rss_per_source,
        "github_limit": args.github_limit,
    }

    print("[PIPELINE] Step 5/5 publish")
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
