from __future__ import annotations

import os
from typing import Any


def select_diversified_top_items(
    items: list[dict[str, Any]], top_k: int
) -> list[dict[str, Any]]:
    relevant = [x for x in items if x.get("is_relevant")]
    relevant.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    if not relevant:
        fallback = sorted(items, key=lambda x: x.get("total_score", 0), reverse=True)[
            :top_k
        ]
        out: list[dict[str, Any]] = []
        for item in fallback:
            y = dict(item)
            y["output_tier"] = "watchlist"
            out.append(y)
        return out

    min_rss = int(os.getenv("MIN_RSS_QUOTA", max(3, top_k // 2)))
    min_github = int(os.getenv("MIN_GITHUB_QUOTA", max(2, top_k // 3)))
    max_per_source = int(os.getenv("MAX_ITEMS_PER_SOURCE", 3))

    min_rss = min(min_rss, top_k)
    min_github = min(min_github, top_k)

    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    source_count: dict[str, int] = {}

    def _try_add(item: dict[str, Any]) -> bool:
        item_id = str(item.get("id", ""))
        source = str(item.get("source", "unknown"))
        if item_id in used_ids:
            return False
        if source_count.get(source, 0) >= max_per_source:
            return False
        selected.append(item)
        used_ids.add(item_id)
        source_count[source] = source_count.get(source, 0) + 1
        return True

    rss_items = [x for x in relevant if x.get("origin_type") == "rss"]
    github_items = [x for x in relevant if x.get("origin_type") == "github"]

    for item in rss_items:
        if len([x for x in selected if x.get("origin_type") == "rss"]) >= min_rss:
            break
        if len(selected) >= top_k:
            break
        _try_add(item)

    for item in github_items:
        if len([x for x in selected if x.get("origin_type") == "github"]) >= min_github:
            break
        if len(selected) >= top_k:
            break
        _try_add(item)

    for item in relevant:
        if len(selected) >= top_k:
            break
        _try_add(item)

    if len(selected) < top_k:
        remaining = [
            x
            for x in sorted(items, key=lambda z: z.get("total_score", 0), reverse=True)
            if str(x.get("id", "")) not in used_ids
        ]
        for item in remaining:
            if len(selected) >= top_k:
                break
            y = dict(item)
            y["output_tier"] = "watchlist"
            selected.append(y)
            used_ids.add(str(item.get("id", "")))

    for item in selected:
        item.setdefault("output_tier", "primary" if item.get("is_relevant") else "watchlist")
    return selected

