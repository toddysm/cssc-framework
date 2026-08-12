import httpx
from fastapi.testclient import TestClient

from cssc_common import GitHubClient, OciRegistryClient
from packages_service.app import create_app
from packages_service.client import PackagesClient

HISTORY_DOC = {
    "schemaVersion": 1,
    "image": "ghcr.io/toddysm/quarantine/python",
    "source": "docker.io/library/python",
    "entries": [
        {
            "sourceTag": "3.14-slim",
            "sourceDigest": "sha256:aaaa",
            "destTag": "3.14-slim",
            "syncedAt": "2026-07-30T06:00:00Z",
            "runUrl": "https://github.com/toddysm/cssc-framework/actions/runs/1",
            "runId": "1",
            "runAttempt": "1",
            "force": False,
        },
        {
            "sourceTag": "3.14-slim",
            "sourceDigest": "sha256:bbbb",
            "destTag": "3.14-slim",
            "syncedAt": "2026-08-13T06:00:00Z",
            "runUrl": "https://github.com/toddysm/cssc-framework/actions/runs/2",
            "runId": "2",
            "runAttempt": "1",
            "force": True,
        },
    ],
}

BLOB_DIGEST = "sha256:blob"
CONFIG_DIGEST = "sha256:config"


def _registry_handler(present: bool):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/token":
            return httpx.Response(200, json={"token": "t"})
        if path.endswith("/manifests/mirror-history"):
            if not present:
                return httpx.Response(404, json={"errors": [{"code": "MANIFEST_UNKNOWN"}]})
            return httpx.Response(
                200,
                json={
                    "schemaVersion": 2,
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "artifactType": "application/vnd.toddysm.mirror-history.v1+json",
                    "config": {
                        "mediaType": "application/vnd.toddysm.mirror-history.v1+json",
                        "digest": CONFIG_DIGEST,
                    },
                    "layers": [
                        {
                            "mediaType": "application/vnd.toddysm.mirror-history.v1+json",
                            "digest": BLOB_DIGEST,
                        }
                    ],
                },
            )
        if path.endswith(f"/blobs/{BLOB_DIGEST}"):
            return httpx.Response(200, json=HISTORY_DOC)
        return httpx.Response(404, json={"message": "not found"})

    return handler


def _app(present: bool = True):
    gh_transport = httpx.MockTransport(
        lambda r: httpx.Response(404, json={"message": "not found"})
    )
    github = GitHubClient(
        client=httpx.Client(base_url="https://api.github.com", transport=gh_transport),
        owner="toddysm",
        repo="cssc-framework",
        cache_ttl=0,
    )
    registry = OciRegistryClient(
        owner="toddysm",
        token="tok",
        client=httpx.Client(
            base_url="https://ghcr.io", transport=httpx.MockTransport(_registry_handler(present))
        ),
    )
    return create_app(PackagesClient(github, registry))


def test_history_returns_entries():
    client = TestClient(_app(present=True))
    response = client.get("/packages/quarantine/python/history")
    assert response.status_code == 200
    body = response.json()
    assert [e["source_digest"] for e in body] == ["sha256:aaaa", "sha256:bbbb"]
    assert body[0]["source_tag"] == "3.14-slim"
    assert body[1]["force"] is True


def test_history_empty_when_tag_absent():
    client = TestClient(_app(present=False))
    response = client.get("/packages/quarantine/python/history")
    assert response.status_code == 200
    assert response.json() == []


def test_history_empty_without_registry():
    gh_transport = httpx.MockTransport(
        lambda r: httpx.Response(404, json={"message": "not found"})
    )
    github = GitHubClient(
        client=httpx.Client(base_url="https://api.github.com", transport=gh_transport),
        owner="toddysm",
        cache_ttl=0,
    )
    client = TestClient(create_app(PackagesClient(github)))
    assert client.get("/packages/quarantine/python/history").json() == []
