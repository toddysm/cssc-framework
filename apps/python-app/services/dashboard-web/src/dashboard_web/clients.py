"""HTTP clients for the capability microservices.

``dashboard-web`` is a backend-for-frontend: it never calls GitHub directly,
only the in-cluster capability services.
"""

from __future__ import annotations

from typing import Any

import httpx


class PackagesServiceClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def get_packages(self, namespace: str) -> list[dict[str, Any]]:
        response = self._client.get(
            f"{self._base}/packages", params={"namespace": namespace}
        )
        response.raise_for_status()
        return response.json()


class IssuesServiceClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def get_issues(
        self,
        image: str | None = None,
        tag: str | None = None,
        state: str = "all",
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"state": state}
        if image:
            params["image"] = image
        if tag:
            params["tag"] = tag
        response = self._client.get(f"{self._base}/issues", params=params)
        response.raise_for_status()
        return response.json()
