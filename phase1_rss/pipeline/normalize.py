from __future__ import annotations

from typing import Any

from pipeline.ingest import canonicalize_url


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = canonicalize_url(item.get("link", "")) or item.get("title", "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out

