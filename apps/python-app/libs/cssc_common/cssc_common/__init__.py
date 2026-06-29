"""Shared building blocks for the CSSC Dashboard microservices.

This package holds cross-cutting concerns that every dashboard service needs:

* :class:`~cssc_common.github.GitHubClient` — a small, cached ``httpx`` wrapper
  around the GitHub REST API.
* :class:`~cssc_common.cache.TTLCache` — a tiny time-to-live cache.
* The shared Pydantic models in :mod:`cssc_common.models`.
* Environment-driven settings in :mod:`cssc_common.config`.
"""

from .cache import TTLCache
from .config import GitHubSettings, github_settings
from .github import GitHubClient
from .models import Cve, MirroredImage, PromotionIssue, Tag

__all__ = [
    "TTLCache",
    "GitHubSettings",
    "github_settings",
    "GitHubClient",
    "Cve",
    "MirroredImage",
    "PromotionIssue",
    "Tag",
]
