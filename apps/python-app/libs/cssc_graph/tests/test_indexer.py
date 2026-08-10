from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ladybug")

from cssc_graph.graph import GraphStore  # noqa: E402
from cssc_graph.indexer import index_data  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_ROOT = REPO_ROOT / "supply-chain-graph"
SCHEMA_DIR = DATA_ROOT / "schema"
EXAMPLES = DATA_ROOT / "examples"

DIGEST2 = "sha256:" + "2" * 64

pytestmark = pytest.mark.skipif(not EXAMPLES.exists(), reason="data root not present")


@pytest.fixture()
def store(tmp_path: Path):
    with GraphStore(tmp_path / "graph") as gs:
        gs.init_schema()
        index_data(gs, EXAMPLES, SCHEMA_DIR)
        yield gs


def _count(store: GraphStore, query: str, params=None) -> int:
    return int(store.scalar(query, params) or 0)


def test_nodes_created(store: GraphStore):
    assert _count(store, "MATCH (o:Occurrence) RETURN count(o)") > 0
    assert _count(store, "MATCH (a:Artifact) RETURN count(a)") > 0


def test_edges_created(store: GraphStore):
    assert _count(store, "MATCH ()-[e:MIRRORED_FROM]->() RETURN count(e)") >= 1
    assert _count(store, "MATCH ()-[e:PROMOTED_FROM]->() RETURN count(e)") >= 1
    assert _count(store, "MATCH ()-[e:BUILT_FROM]->() RETURN count(e)") >= 1
    assert _count(store, "MATCH ()-[e:POINTED_TO]->() RETURN count(e)") >= 1
    assert _count(store, "MATCH ()-[e:RUNS]->() RETURN count(e)") >= 1


def test_built_from_targets_base_repository(store: GraphStore):
    n = _count(
        store,
        "MATCH (:Occurrence)-[:BUILT_FROM]->(b:Occurrence) "
        "WHERE b.repository = 'toddysm/golden/python' RETURN count(*)",
    )
    assert n >= 1


def test_cross_registry_promotion_is_distinct_and_linked(store: GraphStore):
    # The same digest lives as separate occurrences on the two registries.
    registries = {
        row["r"]
        for row in store.query(
            "MATCH (o:Occurrence {digest: $d}) RETURN DISTINCT o.registry AS r",
            {"d": DIGEST2},
        )
    }
    assert {"first.registry.io", "second.registry.io"}.issubset(registries)

    # And the promotion hop between them is preserved.
    linked = _count(
        store,
        "MATCH (to:Occurrence)-[:PROMOTED_FROM]->(from:Occurrence) "
        "WHERE to.registry = 'second.registry.io' AND from.registry = 'first.registry.io' "
        "RETURN count(*)",
    )
    assert linked == 1


def test_indexing_is_idempotent(tmp_path: Path):
    with GraphStore(tmp_path / "graph") as gs:
        gs.init_schema()
        index_data(gs, EXAMPLES, SCHEMA_DIR)
        occ1 = _count(gs, "MATCH (o:Occurrence) RETURN count(o)")
        pf1 = _count(gs, "MATCH ()-[e:PROMOTED_FROM]->() RETURN count(e)")
        pt1 = _count(gs, "MATCH ()-[e:POINTED_TO]->() RETURN count(e)")

        # Re-index the same inputs; nothing should change.
        index_data(gs, EXAMPLES, SCHEMA_DIR)
        assert _count(gs, "MATCH (o:Occurrence) RETURN count(o)") == occ1
        assert _count(gs, "MATCH ()-[e:PROMOTED_FROM]->() RETURN count(e)") == pf1
        assert _count(gs, "MATCH ()-[e:POINTED_TO]->() RETURN count(e)") == pt1
