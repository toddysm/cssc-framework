"""HTTP clients for the capability microservices.

``dashboard-web`` is a backend-for-frontend: it never calls GitHub directly,
only the in-cluster capability services.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class GraphClient(Protocol):
    """The subset of graph-service used by the dashboard (see GraphServiceClient)."""

    def readiness(self) -> dict[str, Any]: ...

    def neighborhood(self, ref: str, depth: int = 3) -> dict[str, Any]: ...

    def referrers(self, ref: str, depth: int = 3) -> dict[str, Any]: ...


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

    def get_tags(self, name: str) -> list[dict[str, Any]]:
        response = self._client.get(f"{self._base}/packages/{name}/tags")
        response.raise_for_status()
        return response.json()

    def get_history(self, name: str) -> list[dict[str, Any]]:
        response = self._client.get(f"{self._base}/packages/{name}/history")
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


class GraphServiceClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout)

    def readiness(self) -> dict[str, Any]:
        """Return the graph index readiness summary (never raises on 503)."""

        response = self._client.get(f"{self._base}/readyz")
        if response.status_code == 503:
            return {"ready": False, "records": 0, "by_kind": {}}
        response.raise_for_status()
        body = response.json()
        return {
            "ready": True,
            "records": body.get("records", 0),
            "by_kind": body.get("byKind", {}),
            "root": body.get("root"),
        }

    def neighborhood(self, ref: str, depth: int = 3) -> dict[str, Any]:
        response = self._client.get(
            f"{self._base}/graph/neighborhood",
            params={"ref": ref, "depth": depth, "format": "json"},
        )
        response.raise_for_status()
        return response.json()

    def referrers(self, ref: str, depth: int = 3) -> dict[str, Any]:
        response = self._client.get(
            f"{self._base}/artifacts/referrers",
            params={"ref": ref, "depth": depth, "format": "json"},
        )
        response.raise_for_status()
        return response.json()
