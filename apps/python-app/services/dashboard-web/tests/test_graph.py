"""Tests for the supply-chain graph view in dashboard-web."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from dashboard_web.app import create_app
from dashboard_web.clients import GraphServiceClient
from dashboard_web.stages.base import StageRegistry
from dashboard_web.stages.observability import GraphProvider

SUBGRAPH = {
    "nodes": [
        {
            "key": "ghcr.io/toddysm/apps/cssc-dashboard/packages-service@sha256:aa",
            "ref": "ghcr.io/toddysm/apps/cssc-dashboard/packages-service",
            "digest": "sha256:aa",
        },
        {
            "key": "ghcr.io/toddysm/golden/python@sha256:bb",
            "ref": "ghcr.io/toddysm/golden/python",
            "digest": "sha256:bb",
        },
    ],
    "edges": [
        {
            "type": "BUILT_FROM",
            "from": "ghcr.io/toddysm/apps/cssc-dashboard/packages-service@sha256:aa",
            "to": "ghcr.io/toddysm/golden/python@sha256:bb",
            "tag": "3.14-slim",
        }
    ],
}


class FakeGraph:
    def __init__(self, ready: bool = True, records: int = 3, by_kind=None, subgraph=None):
        self._readiness = {"ready": ready, "records": records, "by_kind": by_kind or {"ArtifactBuilt": 2}}
        self._subgraph = subgraph if subgraph is not None else SUBGRAPH

    def readiness(self):
        return self._readiness

    def neighborhood(self, ref, depth=3):
        return self._subgraph


def _app(graph: FakeGraph):
    registry = StageRegistry()
    registry.register(GraphProvider(graph))
    return create_app(registry=registry, graph=graph)


def test_provider_metadata():
    provider = GraphProvider(FakeGraph())
    assert provider.stage.id == "observability"
    assert provider.stage.order == 5


def test_fragment_shows_index_summary():
    client = TestClient(_app(FakeGraph(records=4, by_kind={"ArtifactBuilt": 2, "TagObserved": 2})))
    body = client.get("/stages/observability/fragment").text
    assert "4" in body
    assert "ArtifactBuilt: 2" in body


def test_fragment_reports_not_ready():
    client = TestClient(_app(FakeGraph(ready=False, records=0)))
    body = client.get("/stages/observability/fragment").text
    assert "not ready" in body


def test_neighborhood_route_renders_edges():
    client = TestClient(_app(FakeGraph()))
    resp = client.get("/graph/neighborhood", params={"ref": "ghcr.io/toddysm/apps/cssc-dashboard/packages-service:0.1"})
    assert resp.status_code == 200
    assert "BUILT_FROM" in resp.text
    assert "golden/python" in resp.text


def test_neighborhood_route_without_ref_prompts():
    client = TestClient(_app(FakeGraph()))
    assert "Enter a reference" in client.get("/graph/neighborhood").text


def test_neighborhood_route_empty_subgraph():
    client = TestClient(_app(FakeGraph(subgraph={"nodes": [], "edges": []})))
    body = client.get("/graph/neighborhood", params={"ref": "ghcr.io/none:0"}).text
    assert "No graph found" in body


def test_graph_client_readiness_ready():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/readyz"
        return httpx.Response(200, json={"status": "ready", "records": 5, "byKind": {"ArtifactBuilt": 5}})

    client = GraphServiceClient("http://graph", client=httpx.Client(transport=httpx.MockTransport(handler)))
    body = client.readiness()
    assert body == {"ready": True, "records": 5, "by_kind": {"ArtifactBuilt": 5}, "root": None}


def test_graph_client_readiness_not_ready_on_503():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "graph index not ready"})

    client = GraphServiceClient("http://graph", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.readiness()["ready"] is False


def test_graph_client_neighborhood():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph/neighborhood"
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json=SUBGRAPH)

    client = GraphServiceClient("http://graph", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.neighborhood("ghcr.io/x:1")["edges"][0]["type"] == "BUILT_FROM"
