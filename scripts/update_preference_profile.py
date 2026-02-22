from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
FEEDBACK_DIR = ROOT / "feedback"
LIKED_ITEMS_PATH = FEEDBACK_DIR / "liked_items.jsonl"
WEB_FEEDBACK_PATH = FEEDBACK_DIR / "web_feedback.jsonl"
PROFILE_PATH = FEEDBACK_DIR / "preference_profile.json"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _tokenize(text: str) -> list[str]:
    # Keep alnum tokens with a minimum length to reduce noisy words.
    return [t for t in re.findall(r"[a-zA-Z0-9\-_]{3,}", text.lower())]


def _domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def build_profile(events: list[dict]) -> dict:
    source_weights: dict[str, float] = defaultdict(float)
    domain_weights: dict[str, float] = defaultdict(float)
    keyword_weights: dict[str, float] = defaultdict(float)
    positive = 0
    negative = 0

    for e in events:
        label = str(e.get("label", "")).lower()
        score = 0.0
        if label in {"like", "upvote", "favorite"}:
            score = 1.0
            positive += 1
        elif label in {"dislike", "downvote"}:
            score = -1.0
            negative += 1
        if score == 0:
            continue

        source = str(e.get("source", "")).strip()
        if source:
            source_weights[source] += score

        href = str(e.get("url") or e.get("href") or "").strip()
        d = _domain(href)
        if d:
            domain_weights[d] += score

        text = " ".join(
            [
                str(e.get("title", "")),
                str(e.get("note", "")),
                " ".join([str(x) for x in e.get("tags", []) if isinstance(x, str)]),
            ]
        )
        for token in _tokenize(text):
            keyword_weights[token] += score

    # Clamp to keep personalization bounded and predictable.
    def _clamp_map(m: dict[str, float], low: float, high: float) -> dict[str, float]:
        out: dict[str, float] = {}
        for k, v in m.items():
            out[k] = round(max(low, min(high, v)), 2)
        return out

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_weights": _clamp_map(dict(source_weights), -4.0, 4.0),
        "domain_weights": _clamp_map(dict(domain_weights), -3.0, 3.0),
        "keyword_weights": _clamp_map(dict(keyword_weights), -2.0, 2.0),
        "positive_events": positive,
        "negative_events": negative,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build preference profile from feedback signals.")
    p.add_argument("--liked-path", type=Path, default=LIKED_ITEMS_PATH)
    p.add_argument("--web-path", type=Path, default=WEB_FEEDBACK_PATH)
    p.add_argument("--out", type=Path, default=PROFILE_PATH)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    events = _read_jsonl(args.liked_path) + _read_jsonl(args.web_path)
    profile = build_profile(events)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[OK] Preference profile updated: {args.out} "
        f"(positive={profile['positive_events']}, negative={profile['negative_events']})"
    )


if __name__ == "__main__":
    main()

