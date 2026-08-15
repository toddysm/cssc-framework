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


DIGEST3 = "sha256:" + "3" * 64
QUAR_REF = "ghcr.io/toddysm/quarantine/python"


def test_referrers_returns_edge_with_artifact_type(store):
    sub = queries.referrers(store, ref=f"{GOLDEN_REF}@{DIGEST2}")
    assert "REFERS_TO" in {e["type"] for e in sub["edges"]}
    assert "application/vnd.in-toto+json" in {e.get("artifactType") for e in sub["edges"]}


def test_referrers_depth_zero_returns_only_subject(store):
    sub = queries.referrers(store, ref=f"{GOLDEN_REF}@{DIGEST2}", depth=0)
    assert sub["edges"] == []
    assert {n["key"] for n in sub["nodes"]} == {f"{GOLDEN_REF}@{DIGEST2}"}


def test_show_includes_referrers(store):
    data = queries.show(store, f"{GOLDEN_REF}@{DIGEST2}")
    assert data is not None
    assert data["deleted"] is False
    assert any(r.get("artifactType") == "application/vnd.in-toto+json" for r in data["referrers"])


DIGEST4 = "sha256:" + "4" * 64
DIGEST5 = "sha256:" + "5" * 64


def test_platforms_returns_child_manifests(store):
    rows = queries.platforms(store, ref=f"{GOLDEN_REF}@{DIGEST2}")
    pairs = {(r["os"], r["architecture"]) for r in rows}
    assert pairs == {("linux", "amd64"), ("linux", "arm64")}
    assert {r["digest"] for r in rows} == {DIGEST4, DIGEST5}


def test_index_of_maps_child_to_index(store):
    assert queries.index_of(store, f"{GOLDEN_REF}@{DIGEST4}") == f"{GOLDEN_REF}@{DIGEST2}"
    assert queries.index_of(store, f"{GOLDEN_REF}@{DIGEST2}") is None


DIGEST6 = "sha256:" + "6" * 64


def test_referrers_roll_child_attestation_up_to_index(store):
    # The example attaches an attestation (digest 6…) to the amd64 child (digest
    # 4…). Querying the index rolls that referrer up onto the index, tagged with
    # the platform, so no attestation dangles off the child manifest.
    sub = queries.referrers(store, ref=f"{GOLDEN_REF}@{DIGEST2}")
    rolled = [
        e
        for e in sub["edges"]
        if e["from"] == f"{GOLDEN_REF}@{DIGEST6}" and e["to"] == f"{GOLDEN_REF}@{DIGEST2}"
    ]
    assert len(rolled) == 1
    assert rolled[0]["platform"] == "linux/amd64"
    # The child manifest itself is not introduced as a node by the roll-up.
    assert f"{GOLDEN_REF}@{DIGEST4}" not in {n["key"] for n in sub["nodes"]}


def test_referrers_no_rollup_keeps_child_referrers_off_index(store):
    sub = queries.referrers(store, ref=f"{GOLDEN_REF}@{DIGEST2}", rollup=False)
    assert not any(e["from"] == f"{GOLDEN_REF}@{DIGEST6}" for e in sub["edges"])


def test_show_marks_deleted_occurrence(store):
    data = queries.show(store, f"{QUAR_REF}@{DIGEST3}")
    assert data is not None
    assert data["deleted"] is True
    assert data["occurrence"]["deleteReason"] == "promoted"


def test_node_label_disambiguates_by_digest_and_marks_deleted():
    assert queries._node_label({"ref": GOLDEN_REF, "digest": DIGEST2}) == f"{GOLDEN_REF}@222222222222"
    lbl = queries._node_label({"ref": QUAR_REF, "digest": DIGEST3, "deletedAt": "2026-08-09T13:10:10Z"})
    assert lbl.endswith("(deleted)")


def test_cli_referrers(tmp_path: Path):
    from click.testing import CliRunner

    from cssc_graph.cli import cli

    db = tmp_path / "db"
    with GraphStore(db) as gs:
        gs.init_schema()
        index_data(gs, EXAMPLES, SCHEMA_DIR)
    result = CliRunner().invoke(cli, ["referrers", "-d", str(db), "--ref", f"{GOLDEN_REF}@{DIGEST2}"])
    assert result.exit_code == 0, result.output
    assert "REFERS_TO" in result.output
    assert "application/vnd.in-toto+json" in result.output
