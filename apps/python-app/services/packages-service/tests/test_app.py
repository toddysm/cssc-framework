import httpx
from fastapi.testclient import TestClient

from cssc_common.github import GitHubClient
from packages_service.app import create_app
from packages_service.client import PackagesClient

PACKAGES = [
    {
        "name": "quarantine/python",
        "visibility": "private",
        "updated_at": "2026-06-01T00:00:00Z",
        "version_count": 3,
    },
    {
        "name": "quarantine/node",
        "visibility": "private",
        "updated_at": "2026-06-02T00:00:00Z",
        "version_count": 1,
    },
    {
        "name": "golden/python",
        "visibility": "private",
        "updated_at": "2026-06-03T00:00:00Z",
        "version_count": 2,
    },
]

VERSIONS = [
    {
        "name": "sha256:aaa",
        "updated_at": "2026-06-01T00:00:00Z",
        "metadata": {"container": {"tags": ["3.14-slim", "latest"]}},
    },
    {
        "name": "sha256:bbb",
        "updated_at": "2026-05-01T00:00:00Z",
        "metadata": {"container": {"tags": []}},
    },
]


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/packages"):
        return httpx.Response(200, json=PACKAGES)
    if "/versions" in path:
        return httpx.Response(200, json=VERSIONS)
    return httpx.Response(404, json={"message": "not found"})


def _app():
    transport = httpx.MockTransport(_handler)
    http = httpx.Client(base_url="https://api.github.com", transport=transport)
    github = GitHubClient(client=http, owner="toddysm", repo="cssc-framework", cache_ttl=0)
    return create_app(PackagesClient(github))


def test_list_packages_filters_to_namespace():
    client = TestClient(_app())
    response = client.get("/packages", params={"namespace": "quarantine"})
    assert response.status_code == 200
    names = [pkg["name"] for pkg in response.json()]
    assert names == ["quarantine/python", "quarantine/node"]


def test_list_packages_includes_metadata():
    client = TestClient(_app())
    payload = client.get("/packages").json()
    python = next(p for p in payload if p["name"] == "quarantine/python")
    assert python["visibility"] == "private"
    assert python["tag_count"] == 3


def test_list_tags_flattens_versions_and_skips_untagged():
    client = TestClient(_app())
    response = client.get("/packages/quarantine/python/tags")
    assert response.status_code == 200
    body = response.json()
    assert [t["tag"] for t in body] == ["3.14-slim", "latest"]
    assert body[0]["digest"] == "sha256:aaa"


def test_healthz_and_readyz():
    client = TestClient(_app())
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_uses_org_root_for_org_owner():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=PACKAGES)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url="https://api.github.com", transport=transport)
    github = GitHubClient(client=http, owner="acme", owner_type="org", cache_ttl=0)
    PackagesClient(github).list_packages("quarantine")
    assert seen["path"] == "/orgs/acme/packages"
