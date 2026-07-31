"""A minimal OCI registry read client for small JSON artifacts.

The dashboard reads the ``mirror-history`` artifact straight from the registry
(GHCR by default): it resolves a tag to a manifest, then pulls the single JSON
layer blob. This is deliberately tiny — just enough to fetch one JSON artifact —
and takes an injectable ``httpx`` client/transport so it is trivial to unit test
with :class:`httpx.MockTransport`.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

# Reserved tag under which the mirror workflows store the per-repo history
# artifact. It is never a valid upstream image tag to mirror.
MIRROR_HISTORY_TAG = "mirror-history"

_MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


class OciRegistryClient:
    """Fetch a single JSON artifact (manifest + first layer blob) from a registry."""

    def __init__(
        self,
        *,
        registry: str = "ghcr.io",
        owner: str = "",
        token: str | None = None,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._registry = registry
        self._owner = owner
        self._token = token

        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(
                base_url=f"https://{registry}",
                timeout=timeout,
                transport=transport,
            )
            self._owns_client = True

    def _repository(self, name: str) -> str:
        return f"{self._owner}/{name}" if self._owner else name

    def _bearer(self, repository: str) -> str | None:
        """Exchange for a pull token. Anonymous for public repos; Basic-auth
        with the configured token otherwise."""

        headers: dict[str, str] = {}
        if self._token:
            basic = base64.b64encode(
                f"{self._owner or 'x'}:{self._token}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {basic}"
        response = self._client.get(
            "/token",
            params={
                "service": self._registry,
                "scope": f"repository:{repository}:pull",
            },
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("token") or data.get("access_token")

    def fetch_json_artifact(
        self, name: str, reference: str
    ) -> dict[str, Any] | None:
        """Return the parsed JSON of the artifact's first layer blob.

        ``None`` when the reference does not exist (a missing tag is not an
        error), so callers can treat it as "no history yet".
        """

        repository = self._repository(name)
        bearer = self._bearer(repository)
        auth = {"Authorization": f"Bearer {bearer}"} if bearer else {}

        manifest_response = self._client.get(
            f"/v2/{repository}/manifests/{reference}",
            headers={"Accept": _MANIFEST_ACCEPT, **auth},
        )
        if manifest_response.status_code == 404:
            return None
        manifest_response.raise_for_status()

        layers = manifest_response.json().get("layers") or []
        if not layers or not layers[0].get("digest"):
            return None

        blob_response = self._client.get(
            f"/v2/{repository}/blobs/{layers[0]['digest']}",
            headers=auth,
        )
        blob_response.raise_for_status()
        return blob_response.json()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
