from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ladybug")

import yaml  # noqa: E402
from click.testing import CliRunner  # noqa: E402

from cssc_graph.cli import cli  # noqa: E402
from cssc_graph.graph import GraphStore  # noqa: E402
from cssc_graph.indexer import Indexer, index_data  # noqa: E402

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


def test_index_record_rejects_missing_kind(tmp_path: Path):
    with GraphStore(tmp_path / "graph") as gs:
        gs.init_schema()
        with pytest.raises(ValueError):
            Indexer(gs).index_record({"schemaVersion": 1})


def test_destroy_refuses_unsafe_paths():
    with pytest.raises(ValueError):
        GraphStore.destroy(Path.cwd())
    with pytest.raises(ValueError):
        GraphStore.destroy(Path(Path.cwd().anchor))


def test_cli_index_success(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["index", str(EXAMPLES), "--database", str(tmp_path / "g"), "--schema-dir", str(SCHEMA_DIR)],
    )
    assert result.exit_code == 0, result.output
    assert "Indexed" in result.output


def test_cli_index_rebuild_is_repeatable(tmp_path: Path):
    runner = CliRunner()
    args = ["index", str(EXAMPLES), "--database", str(tmp_path / "g"), "--schema-dir", str(SCHEMA_DIR), "--rebuild"]
    assert runner.invoke(cli, args).exit_code == 0
    assert runner.invoke(cli, args).exit_code == 0


def test_cli_index_validation_failure(tmp_path: Path):
    bad = tmp_path / "data"
    bad.mkdir()
    (bad / "bad.yaml").write_text(yaml.safe_dump({"kind": "Nope"}), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        cli, ["index", str(bad), "--database", str(tmp_path / "g"), "--schema-dir", str(SCHEMA_DIR)]
    )
    assert result.exit_code != 0
    assert "nothing indexed" in result.output
