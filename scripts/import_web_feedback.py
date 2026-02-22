from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_FEEDBACK_PATH = ROOT / "feedback" / "web_feedback.jsonl"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import feedback events exported from site localStorage.")
    p.add_argument("--input", type=Path, required=True, help="JSON file exported from page")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input JSON must be an array of feedback events.")

    WEB_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    imported = 0
    with WEB_FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        for row in payload:
            if not isinstance(row, dict):
                continue
            row.setdefault("ts", datetime.now(timezone.utc).isoformat())
            row.setdefault("channel", "web")
            if str(row.get("label", "")).lower() not in {"like", "dislike", "upvote", "downvote", "favorite"}:
                continue
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            imported += 1
    print(f"[OK] Imported feedback events: {imported}")


if __name__ == "__main__":
    main()

