"""Environment-driven configuration shared by the capability services."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubSettings:
    """Settings the capability services need to talk to the GitHub API."""

    owner: str
    repo: str
    api_url: str
    cache_ttl: int
    token: str | None = None


def github_settings() -> GitHubSettings:
    """Build :class:`GitHubSettings` from the process environment.

    Recognised variables:

    * ``GITHUB_TOKEN`` — token with ``read:packages`` and issues read access.
    * ``GITHUB_OWNER`` / ``GITHUB_REPO`` — repository coordinates.
    * ``GITHUB_API_URL`` — defaults to ``https://api.github.com``.
    * ``CACHE_TTL_SECONDS`` — response cache TTL (defaults to ``60``).
    """

    return GitHubSettings(
        owner=os.environ.get("GITHUB_OWNER", ""),
        repo=os.environ.get("GITHUB_REPO", ""),
        api_url=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
        cache_ttl=int(os.environ.get("CACHE_TTL_SECONDS", "60")),
        token=os.environ.get("GITHUB_TOKEN") or None,
    )
