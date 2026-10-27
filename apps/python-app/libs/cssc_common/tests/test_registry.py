import httpx
import pytest

from cssc_common import OciRegistryClient


@pytest.mark.parametrize("injected_client", [False, True])
def test_json_blob_redirect_is_followed_without_forwarding_registry_credentials(injected_client):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/token":
            return httpx.Response(200, json={"token": "test-registry-pull-token"})
        if "/manifests/" in request.url.path:
            return httpx.Response(200, json={"layers": [{"digest": "sha256:blob"}]})
        if "/blobs/" in request.url.path:
            assert request.headers["Authorization"] == "Bearer test-registry-pull-token"
            return httpx.Response(307, headers={"Location": "https://cdn.example.test/blob?sig=test-only"})
        assert request.url.host == "cdn.example.test"
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"schemaVersion": 1, "entries": []})

    transport = httpx.MockTransport(handler)
    if injected_client:
        http = httpx.Client(base_url="https://ghcr.io", transport=transport)
        registry = OciRegistryClient(owner="toddysm", client=http)
    else:
        http = None
        registry = OciRegistryClient(owner="toddysm", transport=transport)
    try:
        assert registry.fetch_json_artifact("quarantine/test", "mirror-history") == {
            "schemaVersion": 1, "entries": [],
        }
        assert len(seen) == 4
    finally:
        registry.close()
        if http is not None:
            http.close()


@pytest.mark.parametrize("status", [404, 503])
def test_redirected_blob_errors_preserve_status_without_exposing_signed_queries(status):
    def handler(request):
        if request.url.path == "/token":
            return httpx.Response(200, json={"token": "test-registry-pull-token"})
        if "/manifests/" in request.url.path:
            return httpx.Response(200, json={"layers": [{"digest": "sha256:blob"}]})
        if "/blobs/" in request.url.path:
            return httpx.Response(307, headers={"Location": "https://cdn.example.test/blob?sig=test-only"})
        return httpx.Response(status)

    registry = OciRegistryClient(owner="toddysm", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(httpx.HTTPStatusError) as failure:
            registry.fetch_json_artifact("quarantine/test", "mirror-history")
        assert failure.value.response.status_code == status
        assert "https://cdn.example.test/blob" in str(failure.value)
        assert "test-only" not in str(failure.value)
        assert "?sig=" not in str(failure.value)
    finally:
        registry.close()
