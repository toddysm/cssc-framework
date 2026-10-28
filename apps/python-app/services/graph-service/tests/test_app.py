"""Tests for the graph-service FastAPI app.

Builds a small temporary data root (a copy of the repo's schemas plus a handful
of event records), indexes it through the real query layer, and exercises the
HTTP journeys. Skipped when the native LadybugDB engine or the repo schemas are
unavailable.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("ladybug")

from fastapi.testclient import TestClient  # noqa: E402
from graph_service.app import create_app  # noqa: E402
from graph_service.config import GraphSettings  # noqa: E402

REPO_SCHEMA = Path(__file__).resolve().parents[5] / "supply-chain-graph" / "schema"

APP_REPO = "toddysm/apps/cssc-dashboard/packages-service"
APP_REF = f"ghcr.io/{APP_REPO}"
DIGEST_APP = "sha256:" + "a" * 64
DIGEST_GOLDEN = "sha256:" + "b" * 64
DIGEST_UP = "sha256:" + "c" * 64
DIGEST_REF = "sha256:" + "d" * 64

SOURCE = {
    "type": "github-actions",
    "workflow": "build / cssc-dashboard",
    "runUrl": "https://github.com/toddysm/cssc-framework/actions/runs/1",
    "runId": "1",
    "runAttempt": "1",
}

RECORDS: list[tuple[str, dict]] = [
    (
        "artifact-built",
        {
            "schemaVersion": 1,
            "kind": "ArtifactBuilt",
            "recordedAt": "2026-08-10T00:00:00Z",
            "source": SOURCE,
            "image": {"registry": "ghcr.io", "repository": APP_REPO, "digest": DIGEST_APP},
            "base": {"name": "ghcr.io/toddysm/golden/python", "digest": DIGEST_GOLDEN, "tag": "3.14-slim"},
        },
    ),
    (
        "artifact-built",
        {
            "schemaVersion": 1,
            "kind": "ArtifactBuilt",
            "recordedAt": "2026-08-10T00:00:00Z",
            "source": SOURCE,
            "image": {"registry": "ghcr.io", "repository": "toddysm/golden/python", "digest": DIGEST_GOLDEN},
            "base": {"name": "docker.io/library/python", "digest": DIGEST_UP, "tag": "3.14-slim"},
        },
    ),
    (
        "tag-observed",
        {
            "schemaVersion": 1,
            "kind": "TagObserved",
            "recordedAt": "2026-08-10T00:00:00Z",
            "source": SOURCE,
            "occurrence": {"registry": "ghcr.io", "repository": APP_REPO},
            "tag": "0.1.0",
            "digest": DIGEST_APP,
            "observedAt": "2026-08-10T00:00:00Z",
        },
    ),
    (
        "artifact-deployed",
        {
            "schemaVersion": 1,
            "kind": "ArtifactDeployed",
            "recordedAt": "2026-08-10T00:00:00Z",
            "source": {**SOURCE, "workflow": "deploy / cssc-dashboard"},
            "image": {"registry": "ghcr.io", "repository": APP_REPO, "digest": DIGEST_APP},
            "environment": {"cluster": "kind-cssc", "namespace": "default"},
            "chart": {"name": "cssc-dashboard", "version": "0.1.2"},
        },
    ),
    (
        "referrer-observed",
        {
            "schemaVersion": 1,
            "kind": "ReferrerObserved",
            "recordedAt": "2026-08-10T00:00:00Z",
            "source": SOURCE,
            "occurrence": {"registry": "ghcr.io", "repository": APP_REPO},
            "subject": {"digest": DIGEST_APP, "tag": "0.1.0"},
            "referrer": {"digest": DIGEST_REF, "artifactType": "application/vnd.in-toto+json"},
            "observedAt": "2026-08-10T00:00:00Z",
        },
    ),
]


def _write_data_root(base: Path, records: list[tuple[str, dict]]) -> Path:
    import shutil

    root = base / "data"
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_SCHEMA, root / "schema")
    for i, (kind_dir, record) in enumerate(records):
        target = root / "events" / kind_dir
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{i}.json").write_text(json.dumps(record), encoding="utf-8")
    return root


def _settings(tmp_path: Path, root: Path, max_depth: int = 6) -> GraphSettings:
    return GraphSettings(
        data_root=root,
        database_path=tmp_path / "db",
        schema_dir=None,
        rebuild_on_startup=True,
        max_depth=max_depth,
    )


@pytest.fixture
def client(tmp_path: Path):
    if not REPO_SCHEMA.exists():
        pytest.skip("repo schema directory not found")
    root = _write_data_root(tmp_path, RECORDS)
    app = create_app(_settings(tmp_path, root))
    with TestClient(app) as test_client:
        yield test_client


def test_healthz_ok(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_reports_indexed_records(client: TestClient) -> None:
    body = client.get("/readyz").json()
    assert body["status"] == "ready"
    assert body["records"] == len(RECORDS)
    assert body["byKind"]["ArtifactBuilt"] == 2


def test_resolve_by_digest(client: TestClient) -> None:
    occurrences = client.get("/artifacts/resolve", params={"digest": DIGEST_APP}).json()["occurrences"]
    assert f"{APP_REF}@{DIGEST_APP}" in occurrences


def test_resolve_requires_a_selector(client: TestClient) -> None:
    assert client.get("/artifacts/resolve").status_code == 400


def test_bases_are_transitive(client: TestClient) -> None:
    body = client.get("/artifacts/bases", params={"ref": f"{APP_REF}@{DIGEST_APP}"}).json()
    edges = {(e["from"], e["to"]) for e in body["edges"]}
    assert (f"{APP_REF}@{DIGEST_APP}", f"ghcr.io/toddysm/golden/python@{DIGEST_GOLDEN}") in edges
    assert (
        f"ghcr.io/toddysm/golden/python@{DIGEST_GOLDEN}",
        f"docker.io/library/python@{DIGEST_UP}",
    ) in edges


def test_derived_is_transitive(client: TestClient) -> None:
    body = client.get("/artifacts/derived", params={"base": f"docker.io/library/python@{DIGEST_UP}"}).json()
    keys = {n["key"] for n in body["nodes"]}
    assert f"{APP_REF}@{DIGEST_APP}" in keys


def test_path_spans_build_lineage(client: TestClient) -> None:
    body = client.get("/artifacts/path", params={"ref": f"{APP_REF}@{DIGEST_APP}"}).json()
    assert len(body["edges"]) == 2


def test_tag_history(client: TestClient) -> None:
    body = client.get("/repositories/tags/history", params={"ref": APP_REF, "tag": "0.1.0"}).json()
    assert body["observations"][0]["digest"] == DIGEST_APP


def test_show_returns_occurrence(client: TestClient) -> None:
    body = client.get("/artifacts/show", params={"ref": f"{APP_REF}@{DIGEST_APP}"}).json()
    assert body["occurrence"]["digest"] == DIGEST_APP


def test_show_unknown_ref_is_404(client: TestClient) -> None:
    missing = "sha256:" + "0" * 64
    assert client.get("/artifacts/show", params={"ref": f"{APP_REF}@{missing}"}).status_code == 404


def test_search_bad_annotation_is_400(client: TestClient) -> None:
    assert client.get("/search", params={"annotation": "no-equals"}).status_code == 400


def test_neighborhood_mermaid(client: TestClient) -> None:
    resp = client.get("/graph/neighborhood", params={"ref": f"{APP_REF}@{DIGEST_APP}", "format": "mermaid"})
    assert resp.headers["content-type"].startswith("text/plain")
    assert "flowchart" in resp.text


def test_neighborhood_cytoscape(client: TestClient) -> None:
    body = client.get(
        "/graph/neighborhood", params={"ref": f"{APP_REF}@{DIGEST_APP}", "format": "cytoscape"}
    ).json()
    assert "elements" in body


def test_referrers_endpoint(client: TestClient) -> None:
    body = client.get("/artifacts/referrers", params={"ref": f"{APP_REF}@{DIGEST_APP}"}).json()
    assert any(
        e["type"] == "REFERS_TO" and e.get("artifactType") == "application/vnd.in-toto+json"
        for e in body["edges"]
    )


def test_referrers_requires_selector(client: TestClient) -> None:
    assert client.get("/artifacts/referrers").status_code == 400


def test_referrers_endpoint_accepts_no_rollup(client: TestClient) -> None:
    body = client.get(
        "/artifacts/referrers",
        params={"ref": f"{APP_REF}@{DIGEST_APP}", "rollup": "false"},
    ).json()
    assert any(
        e["type"] == "REFERS_TO" and e.get("artifactType") == "application/vnd.in-toto+json"
        for e in body["edges"]
    )


def test_provenance_endpoint_json(client: TestClient) -> None:
    body = client.get("/artifacts/provenance", params={"family": "python"}).json()
    assert body["nodes"] and body["edges"]
    assert any(n.get("state") == "present-golden" for n in body["nodes"])
    assert "built" in {e["type"] for e in body["edges"]}


def test_provenance_endpoint_mermaid(client: TestClient) -> None:
    resp = client.get("/artifacts/provenance", params={"family": "python", "format": "mermaid"})
    assert resp.status_code == 200
    assert resp.text.strip().startswith("flowchart")


def test_provenance_endpoint_unknown_family_is_empty(client: TestClient) -> None:
    body = client.get("/artifacts/provenance", params={"family": "does-not-exist"}).json()
    assert body == {"nodes": [], "edges": []}



def test_depth_is_capped(client: TestClient, tmp_path: Path) -> None:
    # A max_depth of 1 must stop bases traversal at the first hop.
    root = _write_data_root(tmp_path / "capped", RECORDS)
    app = create_app(_settings(tmp_path / "capped", root, max_depth=1))
    with TestClient(app) as capped:
        body = capped.get("/artifacts/bases", params={"ref": f"{APP_REF}@{DIGEST_APP}", "depth": 10}).json()
    assert len(body["edges"]) == 1


def test_rebuild_endpoint(client: TestClient) -> None:
    body = client.post("/index/rebuild").json()
    assert body["status"] == "ok"
    assert body["records"] == len(RECORDS)


def test_not_ready_when_data_invalid(tmp_path: Path) -> None:
    if not REPO_SCHEMA.exists():
        pytest.skip("repo schema directory not found")
    bad = [("artifact-built", {"schemaVersion": 1, "kind": "ArtifactBuilt", "recordedAt": "x"})]
    root = _write_data_root(tmp_path, bad)
    app = create_app(_settings(tmp_path, root))
    with TestClient(app) as broken:
        assert broken.get("/healthz").status_code == 200
        assert broken.get("/readyz").status_code == 503
        assert broken.get("/artifacts/path", params={"ref": f"{APP_REF}@{DIGEST_APP}"}).status_code == 503


def test_unresolved_references_are_visible_in_permissive_readiness(client: TestClient) -> None:
    """Default indexing remains ready but exposes missing base-image evidence."""
    body = client.get("/readyz").json()
    assert any("unresolved occurrence" in item and "$.base" in item for item in body["diagnostics"])


def test_strict_references_fail_readiness_and_rebuild(tmp_path: Path) -> None:
    """Strict service indexing reports missing evidence instead of serving a partial graph."""
    root = _write_data_root(tmp_path, RECORDS)
    settings = replace(_settings(tmp_path, root), strict_references=True)
    with TestClient(create_app(settings)) as strict:
        assert strict.get("/healthz").status_code == 200
        assert strict.get("/readyz").status_code == 503
        response = strict.post("/index/rebuild")
        assert response.status_code == 422
        assert any("$.base" in diagnostic for diagnostic in response.json()["detail"])


def test_strict_references_resolve_later_input_evidence(tmp_path: Path) -> None:
    """A later source observation resolves an earlier base reference in strict mode."""
    upstream = {
        "schemaVersion": 1, "kind": "ArtifactObserved", "recordedAt": "2026-08-10T00:00:00Z",
        "source": SOURCE,
        "artifact": {"digest": DIGEST_UP},
        "occurrence": {"registry": "docker.io", "repository": "library/python", "digest": DIGEST_UP},
    }
    root = _write_data_root(tmp_path, [*RECORDS, ("artifact-observed", upstream)])
    with TestClient(create_app(replace(_settings(tmp_path, root), strict_references=True))) as strict:
        response = strict.get("/readyz")
        assert response.status_code == 200 and response.json()["diagnostics"] == []


def test_http_history_and_show_preserve_deployment_events(tmp_path: Path) -> None:
    """The HTTP query and artifact details share append-only deployment history."""
    first = next(record for kind, record in RECORDS if kind == "artifact-deployed")
    second = deepcopy(first)
    second["recordedAt"] = "2026-08-11T00:00:00Z"
    second["chart"]["version"] = "0.1.3"
    root = _write_data_root(tmp_path, [*RECORDS, ("artifact-deployed", second)])
    with TestClient(create_app(_settings(tmp_path, root))) as client:
        rows = client.get("/artifacts/deployments", params={"ref": APP_REF}).json()["deployments"]
        assert len(rows) == 2 and rows[0]["eventId"] != rows[1]["eventId"]
        shown = client.get("/artifacts/show", params={"ref": f"{APP_REF}@{DIGEST_APP}"}).json()
        assert shown["deployments"] == rows
        assert client.post("/index/rebuild").status_code == 200
        assert client.get("/artifacts/deployments", params={"ref": APP_REF}).json()["deployments"] == rows


def test_http_tag_intervals_and_ambiguous_resolution(tmp_path: Path) -> None:
    """Conflicting observations return explicit unknown bounds and no arbitrary current target."""
    first = next(record for kind, record in RECORDS if kind == "tag-observed")
    second = {**first, "digest": DIGEST_GOLDEN}
    root = _write_data_root(tmp_path, [*RECORDS, ("tag-observed", second)])
    with TestClient(create_app(_settings(tmp_path, root))) as client:
        rows = client.get("/repositories/tags/history", params={"ref": APP_REF, "tag": "0.1.0"}).json()["observations"]
        assert len(rows) == 2 and all(row["ambiguous"] for row in rows)
        assert all(row["validFrom"] is None for row in rows)
        assert client.get("/artifacts/resolve", params={"ref": f"{APP_REF}:0.1.0"}).json()["occurrences"] == []


def test_strict_reference_environment_configuration(monkeypatch) -> None:
    """Operators can opt into strict references without changing default callers."""
    from graph_service.config import graph_settings

    monkeypatch.delenv("STRICT_REFERENCES", raising=False)
    assert graph_settings().strict_references is False
    monkeypatch.setenv("STRICT_REFERENCES", "true")
    assert graph_settings().strict_references is True
