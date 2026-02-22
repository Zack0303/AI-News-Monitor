from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LIKED_ITEMS_PATH = ROOT / "feedback" / "liked_items.jsonl"


def infer_source(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if "github.com" in host:
        return "GitHub"
    if "openai.com" in host:
        return "OpenAI Blog"
    if "huggingface.co" in host:
        return "Hugging Face"
    return host or "manual"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append a manually liked item for preference learning.")
    p.add_argument("--url", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--source", default="")
    p.add_argument("--tags", default="", help="Comma-separated tags, e.g. agent,infra,benchmark")
    p.add_argument("--note", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    tags = [x.strip() for x in args.tags.split(",") if x.strip()]
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "url": args.url.strip(),
        "title": args.title.strip(),
        "source": args.source.strip() or infer_source(args.url),
        "label": "like",
        "tags": tags,
        "note": args.note.strip(),
    }
    LIKED_ITEMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LIKED_ITEMS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[OK] Added liked item: {row['url']}")


if __name__ == "__main__":
    main()

