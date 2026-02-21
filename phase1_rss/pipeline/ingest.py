from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

import feedparser
import requests

from config import GITHUB_SEARCH_ENDPOINT, RSS_SOURCES, github_query_for_recent


def canonicalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        clean = p._replace(query="", fragment="")
        return urlunparse(clean)
    except Exception:
        return url.strip()


def fetch_rss_items(max_items_per_source: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for source in RSS_SOURCES:
        try:
            feed = feedparser.parse(source.url)
        except Exception as exc:
            print(f"[WARN] RSS source failed: {source.name}: {exc}")
            continue
        for entry in (feed.entries or [])[:max_items_per_source]:
            title = (entry.get("title") or "").strip()
            link = canonicalize_url(entry.get("link", ""))
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            published = (
                entry.get("published")
                or entry.get("updated")
                or datetime.now(timezone.utc).isoformat()
            )
            if not title or not link:
                continue
            items.append(
                {
                    "id": f"rss::{source.name}::{link}",
                    "source": source.name,
                    "title": title,
                    "link": link,
                    "content": summary,
                    "author": entry.get("author", ""),
                    "published_at": str(published),
                    "origin_type": "rss",
                }
            )
    return items


def fetch_github_items(limit: int, token: str | None) -> list[dict[str, Any]]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    params = {
        "q": github_query_for_recent(days=7),
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 50),
        "page": 1,
    }
    resp = requests.get(
        GITHUB_SEARCH_ENDPOINT, params=params, headers=headers, timeout=30
    )
    resp.raise_for_status()
    payload = resp.json()
    items: list[dict[str, Any]] = []
    for repo in payload.get("items", [])[:limit]:
        link = canonicalize_url(repo.get("html_url", ""))
        name = repo.get("full_name", "unknown/repo")
        title = f"{name} (GitHub)"
        desc = repo.get("description") or ""
        stars = int(repo.get("stargazers_count", 0))
        forks = int(repo.get("forks_count", 0))
        pushed_at = repo.get("pushed_at", "")
        content = (
            f"{desc}\nStars: {stars}\nForks: {forks}\n"
            f"Language: {repo.get('language')}\nLast push: {pushed_at}"
        )
        items.append(
            {
                "id": f"github::{name}",
                "source": "GitHub Search",
                "title": title,
                "link": link,
                "content": content,
                "author": (repo.get("owner") or {}).get("login", ""),
                "published_at": pushed_at or datetime.now(timezone.utc).isoformat(),
                "origin_type": "github",
            }
        )
    return items

