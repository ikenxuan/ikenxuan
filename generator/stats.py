"""GitHub stats for the info panel.

Needs a token. Order of resolution: $GITHUB_TOKEN / $GH_TOKEN, then the gh CLI,
then the committed cache. The cache is written on every successful fetch, so a
build without a token -- or one that meets a rate limit -- still produces the
last known-good card instead of failing.
"""
import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
from typing import cast

import requests

from generator import config
from generator.models import GitHubUser, Language, ProfileStats

_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    name
    followers { totalCount }
    following { totalCount }
    createdAt
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection { totalCommitContributions }
  }
}
"""


def _token() -> str | None:
    # ACCESS_TOKEN first: a personal token sees the whole account, where an
    # Actions GITHUB_TOKEN sees only the repository it was issued for.
    for name in ("ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        result = subprocess.run([gh, "auth", "token"], capture_output=True,
                                text=True, timeout=config.GITHUB_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout or "").strip() or None


def _fetch(login: str, token: str) -> GitHubUser:
    response = requests.post(
        config.GITHUB_API,
        json={"query": _QUERY, "variables": {"login": login}},
        headers={"Authorization": f"bearer {token}"},
        timeout=config.GITHUB_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError(f"GitHub API returned HTTP {response.status_code}")
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"GitHub API error: {body['errors'][0].get('message')}")
    # The one unchecked step, and it is unchecked in every language: JSON off the
    # wire has no schema at runtime. models.GitHubUser states what we expect, and
    # every read after this point is checked against it.
    return cast(GitHubUser, body["data"]["user"])


def _aggregate(user: GitHubUser) -> ProfileStats:
    """Fold per-repository language breakdowns into one size-ordered list."""
    sizes: dict[str, Language] = {}
    for repo in user["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            entry = sizes.setdefault(
                name, {"name": name, "color": edge["node"]["color"], "size": 0})
            entry["size"] += edge["size"]

    languages = sorted(sizes.values(), key=lambda item: -item["size"])
    return {
        "login": user["login"],
        "name": user["name"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(repo["stargazerCount"] for repo in user["repositories"]["nodes"]),
        "commits_12mo": user["contributionsCollection"]["totalCommitContributions"],
        "followers": user["followers"]["totalCount"],
        "following": user["following"]["totalCount"],
        "created_at": user["createdAt"][:10],
        "languages": languages,
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _read_cache() -> ProfileStats | None:
    path = pathlib.Path(config.STATS_CACHE_PATH)
    if not path.exists():
        return None
    try:
        return cast(ProfileStats, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _write_cache(stats: ProfileStats) -> None:
    path = pathlib.Path(config.STATS_CACHE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")


def collect(login: str = config.USERNAME, offline: bool = False) -> ProfileStats:
    cached = _read_cache()

    if offline:
        if cached is None:
            raise RuntimeError("--offline given but no cache at " + config.STATS_CACHE_PATH)
        return cached

    token = _token()
    if token is None:
        if cached is None:
            raise RuntimeError(
                "No GitHub token found and no cache to fall back on.\n"
                "Set ACCESS_TOKEN or GITHUB_TOKEN, log in with `gh auth login`, or "
                "run with --offline after a successful fetch.")
        print("No GitHub token; using cached stats.")
        return cached

    try:
        stats = _aggregate(_fetch(login, token))
    except (RuntimeError, requests.RequestException) as error:
        # A nightly build should not go red because GitHub had a bad minute. The
        # card is then a day stale, which "fetched_at" makes visible.
        if cached is None:
            raise
        print(f"GitHub API unavailable ({error}); using cached stats.")
        return cached

    # The API answers under-scoped tokens with partial data and a 200, so this
    # cannot be caught by status code. Compare against the cache instead.
    if cached is not None and stats["repos"] < cached["repos"] * config.STATS_MIN_REPO_RATIO:
        print(f"Fetched {stats['repos']} repositories, but the cache has "
              f"{cached['repos']}. That size of drop means the token cannot see "
              f"every repository -- an Actions GITHUB_TOKEN only sees its own. "
              f"Keeping cached stats. Set an ACCESS_TOKEN secret with read:user "
              f"scope to fix this.")
        return cached

    _write_cache(stats)
    return stats
