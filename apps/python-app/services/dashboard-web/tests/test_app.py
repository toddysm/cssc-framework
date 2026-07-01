from fastapi.testclient import TestClient

from dashboard_web.app import create_app
from dashboard_web.stages.acquisition import AcquisitionProvider
from dashboard_web.stages.base import StageRegistry


class FakePackages:
    def get_packages(self, namespace):
        return [
            {
                "name": "quarantine/python",
                "visibility": "private",
                "updated_at": "2026-06-01T00:00:00Z",
                "tag_count": 2,
            }
        ]


class FakeIssues:
    def get_issues(self, image=None, tag=None, state="all"):
        return [
            {
                "number": 77,
                "title": "Promotion blocked: ghcr.io/toddysm/quarantine/python:3.14-slim",
                "url": "https://github.com/toddysm/cssc-framework/issues/77",
                "state": "open",
                "outcome": "pending",
                "image": "ghcr.io/toddysm/quarantine/python",
                "tag": "3.14-slim",
                "blocking_cves": ["CVE-2024-1234"],
            }
        ]


def _app():
    registry = StageRegistry()
    registry.register(
        AcquisitionProvider(
            FakePackages(),
            FakeIssues(),
            namespace="quarantine",
            cve_base_url="https://nvd.nist.gov/vuln/detail/",
        )
    )
    return create_app(registry=registry)


def test_index_renders_stage_sections():
    client = TestClient(_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Acquisition" in response.text
    assert "/stages/acquisition/fragment" in response.text


def test_fragment_renders_table_with_cve_links():
    client = TestClient(_app())
    response = client.get("/stages/acquisition/fragment")
    assert response.status_code == 200
    body = response.text
    assert "quarantine/python" in body
    assert "#77" in body
    assert 'href="https://nvd.nist.gov/vuln/detail/CVE-2024-1234"' in body
    assert 'target="_blank"' in body
    assert 'rel="noopener"' in body
    assert "Open" in body


def test_unknown_stage_returns_404():
    client = TestClient(_app())
    assert client.get("/stages/does-not-exist/fragment").status_code == 404


def test_healthz_and_readyz():
    client = TestClient(_app())
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
