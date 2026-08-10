from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ladybug")

from cssc_graph import queries  # noqa: E402
from cssc_graph.graph import GraphStore  # noqa: E402
from cssc_graph.indexer import index_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_ROOT = REPO_ROOT / "supply-chain-graph"
SCHEMA_DIR = DATA_ROOT / "schema"
EXAMPLES = DATA_ROOT / "examples"

DIGEST1 = "sha256:" + "1" * 64
DIGEST2 = "sha256:" + "2" * 64
GOLDEN_REF = "ghcr.io/toddysm/golden/python"
GOLDEN1_KEY = f"{GOLDEN_REF}@{DIGEST1}"
ISSUES_REF = "ghcr.io/toddysm/apps/cssc-dashboard/issues-service"

pytestmark = pytest.mark.skipif(not EXAMPLES.exists(), reason="data root not present")


@pytest.fixture()
def store(tmp_path: Path):
    with GraphStore(tmp_path / "graph") as gs:
        gs.init_schema()
        index_data(gs, EXAMPLES, SCHEMA_DIR)
        yield gs


def test_path_of_digest_connects_mirror_and_promotions(store):
    sub = queries.path(store, digest=DIGEST2)
    assert len(sub["nodes"]) >= 5
    types = {e["type"] for e in sub["edges"]}
    assert "MIRRORED_FROM" in types
    assert "PROMOTED_FROM" in types


def test_tag_history_is_chronological(store):
    history = queries.tag_history(store, GOLDEN_REF, "3.14-slim")
    assert history
    assert history[0]["digest"] == DIGEST2
    observed = [h["observedAt"] for h in history]
    assert observed == sorted(observed)


def test_bases_finds_base_image(store):
    sub = queries.bases(store, ISSUES_REF)
    refs = {n["ref"] for n in sub["nodes"]}
    assert GOLDEN_REF in refs


def test_derived_finds_built_image(store):
    sub = queries.derived(store, GOLDEN_REF)
    refs = {n["ref"] for n in sub["nodes"]}
    assert ISSUES_REF in refs


def test_find_by_annotation(store):
    rows = queries.find(store, annotation="com.toddysm.image.base.tag=3.14-slim")
    assert any(r["ref"] == GOLDEN_REF for r in rows)


def test_find_by_type(store):
    rows = queries.find(store, artifact_type="application/vnd.oci.image.index.v1+json")
    assert rows


def test_show_returns_annotations(store):
    data = queries.show(store, GOLDEN1_KEY)
    assert data is not None
    names = {a["name"] for a in data["annotations"]}
    assert "com.toddysm.image.base.tag" in names


def test_export_builders(store):
    sub = queries.path(store, digest=DIGEST2)
    mermaid = queries.to_mermaid(sub)
    assert mermaid.startswith("flowchart")
    cyto = queries.to_cytoscape(sub)
    assert cyto["elements"]


def test_traverse_includes_seed_at_depth_zero(store):
    sub = queries.traverse(store, [GOLDEN1_KEY], queries.PATH_RELS, "both", 0)
    keys = {n["key"] for n in sub["nodes"]}
    assert GOLDEN1_KEY in keys
    assert sub["edges"] == []


def test_mermaid_label_escaping():
    assert queries._mermaid_label('a"b\nc') == "a#quot;b c"
