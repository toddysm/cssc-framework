"""A small, cached ``httpx`` wrapper around the GitHub REST API.

The client is intentionally thin: it adds authentication, a default API
version header, response caching, and ``Link``-header pagination. Callers pass
in either a token (the client builds its own ``httpx.Client``) or a
pre-built ``httpx.Client`` — the latter makes the client trivial to unit test
with :class:`httpx.MockTransport`.
"""

from __future__ import annotations

from typing import Any, Hashable

import httpx

from .cache import TTLCache


class GitHubClient:
    def __init__(
        self,
        *,
        token: str | None = None,
        owner: str = "",
        repo: str = "",
        owner_type: str = "user",
        api_url: str = "https://api.github.com",
        cache_ttl: int = 60,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._owner = owner
        self._repo = repo
        self._owner_type = owner_type
        self._api_url = api_url.rstrip("/")
        self._cache = TTLCache(cache_ttl)

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            self._client = httpx.Client(
                base_url=self._api_url,
                headers=headers,
                timeout=timeout,
                transport=transport,
            )
            self._owns_client = True

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def owner_type(self) -> str:
        return self._owner_type

    @property
    def repo(self) -> str:
        return self._repo

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a single JSON document (cached)."""

        key: Hashable = ("get", path, _freeze(params))
        return self._cache.get_or_set(
            key, lambda: self._request(path, params).json()
        )

    def get_all(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        items_key: str | None = None,
    ) -> list[Any]:
        """GET every page of a paginated endpoint (cached).

        When ``items_key`` is given (for example ``"items"`` for the Search
        API) each page is an object whose list lives under that key; otherwise
        each page is itself a JSON array.
        """

        key: Hashable = ("get_all", path, _freeze(params), items_key)
        return self._cache.get_or_set(
            key, lambda: self._collect(path, params, items_key)
        )

    def _collect(
        self,
        path: str,
        params: dict[str, Any] | None,
        items_key: str | None,
    ) -> list[Any]:
        results: list[Any] = []
        next_url: str | None = path
        next_params = dict(params or {})
        while next_url:
            response = self._request(next_url, next_params or None)
            data = response.json()
            page = data.get(items_key, []) if items_key else data
            results.extend(page)
            # GitHub's Link header carries the full next URL (query included),
            # so subsequent requests drop the original params.
            next_url = _next_link(response.headers.get("link"))
            next_params = {}
        return results

    def _request(
        self, path: str, params: dict[str, Any] | None
    ) -> httpx.Response:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _freeze(params: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if not params:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in params.items()))


def _next_link(link_header: str | None) -> str | None:
    """Extract the ``rel="next"`` URL from a GitHub ``Link`` header."""

    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        for attr in segments[1:]:
            if attr.strip() == 'rel="next"':
                return url
    return None
