from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests


@dataclass
class RepoIdentity:
    owner: str
    repo: str


def parse_repo_url(url: str) -> RepoIdentity | None:
    try:
        p = urlparse(url.strip())
        if "github.com" not in p.netloc.lower():
            return None
        parts = [x for x in p.path.split("/") if x]
        if len(parts) < 2:
            return None
        return RepoIdentity(owner=parts[0], repo=parts[1].replace(".git", ""))
    except Exception:
        return None


def _days_since(iso_str: str | None) -> int:
    if not iso_str:
        return 365
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, (now - dt).days)
    except Exception:
        return 365


def check_github_quality(repo_url: str, github_token: str | None = None) -> dict[str, Any]:
    ident = parse_repo_url(repo_url)
    if not ident:
        return {
            "repo_url": repo_url,
            "ok": False,
            "error": "Not a valid GitHub repository URL.",
            "quality_score": 0,
        }

    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    repo_api = f"https://api.github.com/repos/{ident.owner}/{ident.repo}"
    resp = requests.get(repo_api, headers=headers, timeout=30)
    if resp.status_code >= 400:
        return {
            "repo_url": repo_url,
            "ok": False,
            "error": f"GitHub API error: {resp.status_code}",
            "quality_score": 0,
        }
    data = resp.json()

    stars = int(data.get("stargazers_count", 0))
    forks = int(data.get("forks_count", 0))
    watchers = int(data.get("subscribers_count", 0))
    open_issues = int(data.get("open_issues_count", 0))
    archived = bool(data.get("archived", False))
    disabled = bool(data.get("disabled", False))
    pushed_at = data.get("pushed_at")
    updated_at = data.get("updated_at")
    default_branch = data.get("default_branch", "main")

    last_active_days = min(_days_since(pushed_at), _days_since(updated_at))

    # Lightweight heuristic quality score (0-100)
    score = 0.0
    score += min(35.0, math.log10(max(stars, 1)) * 10.0)
    score += min(20.0, math.log10(max(forks, 1)) * 9.0)
    score += min(10.0, math.log10(max(watchers, 1)) * 8.0)

    if last_active_days <= 7:
        score += 25
    elif last_active_days <= 30:
        score += 18
    elif last_active_days <= 90:
        score += 10
    elif last_active_days <= 180:
        score += 5

    if open_issues > 1000:
        score -= 6
    elif open_issues > 300:
        score -= 3

    if archived or disabled:
        score -= 40

    quality_score = max(0, min(100, round(score, 1)))

    reasons: list[str] = []
    reasons.append(f"Stars={stars}, Forks={forks}, Watchers={watchers}")
    reasons.append(f"Last active {last_active_days} days ago on branch {default_branch}")
    if archived:
        reasons.append("Repository is archived.")
    if disabled:
        reasons.append("Repository is disabled.")
    if open_issues > 300:
        reasons.append(f"Open issues high ({open_issues}).")

    if quality_score >= 75:
        recommendation = "high-priority"
    elif quality_score >= 55:
        recommendation = "watchlist"
    else:
        recommendation = "low-priority"

    return {
        "repo_url": repo_url,
        "ok": True,
        "owner": ident.owner,
        "repo": ident.repo,
        "stars": stars,
        "forks": forks,
        "watchers": watchers,
        "open_issues": open_issues,
        "last_active_days": last_active_days,
        "archived": archived,
        "disabled": disabled,
        "quality_score": quality_score,
        "recommendation": recommendation,
        "reasons": reasons,
    }
