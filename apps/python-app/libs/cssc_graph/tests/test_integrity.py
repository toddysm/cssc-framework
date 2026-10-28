"""Regression coverage for reference integrity and evidence-preserving history."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("ladybug")

from cssc_graph import queries
from cssc_graph.cli import cli
from cssc_graph.graph import GraphStore
from cssc_graph.indexer import Indexer, index_data
from cssc_graph.references import UnresolvedReferences, reference_diagnostics

SCHEMAS = Path(__file__).resolve().parents[5] / "supply-chain-graph/schema"
DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
REF = "ghcr.io/example/app"
OCCURRENCE = {"registry": "ghcr.io", "repository": "example/app", "digest": DIGEST}
SOURCE = {"type": "human", "workflow": "integrity fixture"}


def observed(digest: str = DIGEST) -> dict:
    """Declare one independently observed artifact occurrence."""
    return {
        "schemaVersion": 1,
        "kind": "ArtifactObserved",
        "recordedAt": "2026-10-28T00:00:00Z",
        "source": SOURCE,
        "artifact": {"digest": digest},
        "occurrence": {**OCCURRENCE, "digest": digest},
    }


def deployed(at: str = "2026-10-28T01:00:00Z", version: str = "1") -> dict:
    """Make a deployment observation with independently variable event evidence."""
    return {
        "schemaVersion": 1,
        "kind": "ArtifactDeployed",
        "recordedAt": at,
        "source": SOURCE,
        "image": OCCURRENCE,
        "environment": {"cluster": "test", "namespace": "demo"},
        "chart": {"name": "app", "version": version},
    }


def tag(at: str, digest: str = DIGEST) -> dict:
    """Observe a tag target at a timestamp, preserving offsets for ordering tests."""
    return {
        "schemaVersion": 1,
        "kind": "TagObserved",
        "recordedAt": at,
        "observedAt": at,
        "source": SOURCE,
        "occurrence": {"registry": "ghcr.io", "repository": "example/app"},
        "tag": "stable",
        "digest": digest,
    }


@pytest.fixture
def store(tmp_path: Path):
    """Own a real ephemeral graph for each integrity regression."""
    with GraphStore(tmp_path / "db") as database:
        database.init_schema()
        yield database


def test_reference_diagnostics_are_independent_of_file_order():
    """A later declaration resolves a reference without order-dependent warnings."""
    records = [(Path("deploy.json"), deployed()), (Path("observed.json"), observed())]
    assert (
        reference_diagnostics(records)
        == reference_diagnostics(list(reversed(records)))
        == []
    )
    missing = reference_diagnostics(records[:1])
    assert len(missing) == 1
    assert missing[0].file == Path("deploy.json") and missing[0].location == "$.image"
    assert f"{REF}@{DIGEST}" in missing[0].message
    assert missing[0].severity == "warning"


def test_strict_reference_check_writes_nothing(store: GraphStore, tmp_path: Path):
    """Strict indexing rejects dangling references before writing any graph facts."""
    (tmp_path / "deploy.json").write_text(json.dumps(deployed()))
    with pytest.raises(UnresolvedReferences):
        index_data(store, tmp_path, SCHEMAS, strict_references=True)
    assert store.scalar("MATCH (o:Occurrence) RETURN count(o)") == 0


def test_permissive_indexing_reports_but_preserves_missing_occurrence(
    store: GraphStore, tmp_path: Path
):
    """The legacy permissive path still indexes, but returns actionable warnings."""
    (tmp_path / "deploy.json").write_text(json.dumps(deployed()))
    stats = index_data(store, tmp_path, SCHEMAS)
    assert len(stats.diagnostics) == 1
    assert store.scalar("MATCH (o:Occurrence) RETURN count(o)") == 1


def test_cli_strict_does_not_destroy_an_existing_database(
    store: GraphStore, tmp_path: Path
):
    """An invalid strict rebuild must not erase a previously indexed database."""
    Indexer(store).index_record(observed())
    store.close()
    root = tmp_path / "input"
    root.mkdir()
    (root / "deploy.json").write_text(json.dumps(deployed()))
    result = CliRunner().invoke(
        cli,
        [
            "index",
            str(root),
            "-d",
            str(tmp_path / "db"),
            "--schema-dir",
            str(SCHEMAS),
            "--rebuild",
            "--strict-references",
        ],
    )
    assert result.exit_code == 1 and "deploy.json" in result.output
    with GraphStore(tmp_path / "db") as existing:
        assert existing.scalar("MATCH (o:Occurrence) RETURN count(o)") == 1


def test_deployment_events_are_append_only_and_idempotent(store: GraphStore):
    """Different observations survive even when they deploy the same image."""
    indexer = Indexer(store)
    records = [deployed(), deployed("2026-10-28T02:00:00Z"), deployed(version="2")]
    for record in records + list(reversed(records)):
        indexer.index_record(record)
    history = queries.deployment_history(store, REF)
    assert len(history) == 3
    assert len({row["eventId"] for row in history}) == 3
    assert {row["chartVersion"] for row in history} == {"1", "2"}
    assert len(queries.show(store, f"{REF}@{DIGEST}")["deployments"]) == 3


def test_deployment_evidence_changes_are_not_overwritten(store: GraphStore):
    """Distinct source evidence at the same timestamp remains independently inspectable."""
    first = deployed()
    second = deepcopy(first)
    second["source"] = {**SOURCE, "workflow": "another observation"}
    Indexer(store).index_records([first, second, first])
    history = queries.deployment_history(store, REF)
    assert len(history) == 2
    assert {row["source"]["workflow"] for row in history} == {
        "integrity fixture",
        "another observation",
    }


def test_intervals_merge_repeated_targets_and_sort_real_instants(store: GraphStore):
    """Offset-aware order and repeated observations define a single observed window."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T03:00:00+02:00", OTHER),
            tag("2026-10-28T00:00:00Z"),
            tag("2026-10-28T00:30:00Z"),
        ]
    )
    history = queries.tag_history(store, REF, "stable")
    assert [row["digest"] for row in history] == [DIGEST, DIGEST, OTHER]
    assert history[0]["validFrom"] == history[1]["validFrom"] == "2026-10-28T00:00:00Z"
    assert (
        history[0]["validUntil"] == history[1]["validUntil"] == "2026-10-28T01:00:00Z"
    )
    assert history[-1]["validUntil"] is None


def test_conflicting_tag_observations_do_not_fabricate_intervals_or_current_target(
    store: GraphStore,
):
    """Equivalent timestamps with different digests are ambiguous regardless of file order."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T01:00:00+01:00", OTHER),
            tag("2026-10-28T00:00:00Z"),
        ]
    )
    history = queries.tag_history(store, REF, "stable")
    assert len(history) == 2
    assert all(
        row["ambiguous"] and row["validFrom"] is None and row["validUntil"] is None
        for row in history
    )
    assert queries.resolve_seed(store, ref=f"{REF}:stable") == []


def test_ambiguous_next_observation_does_not_assert_a_known_end(store: GraphStore):
    """Conflicting future evidence leaves the preceding interval's upper bound unknown."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T00:00:00Z"),
            tag("2026-10-28T01:00:00Z"),
            tag("2026-10-28T02:00:00+01:00", OTHER),
        ]
    )
    assert queries.tag_history(store, REF, "stable")[0]["validUntil"] is None


@pytest.mark.parametrize(
    "kind,position",
    [
        ("ArtifactBuilt", "$.base"),
        ("ArtifactPromoted", "$.from"),
        ("ReferrerObserved", "$.subject"),
        ("ArtifactDeleted", "$.digest"),
    ],
)
def test_all_reference_positions_have_actionable_locations(kind: str, position: str):
    """Every reference-only record position reports the missing occurrence."""
    record = {
        "kind": kind,
        "image": {**OCCURRENCE, "digest": OTHER},
        "base": {"name": REF, "digest": DIGEST},
        "from": OCCURRENCE,
        "to": {**OCCURRENCE, "digest": OTHER},
        "occurrence": {"registry": "ghcr.io", "repository": "example/app"},
        "digest": DIGEST,
        "subject": {"digest": DIGEST},
        "referrer": {"digest": OTHER},
    }
    diagnostics = reference_diagnostics([(Path("event.json"), record)], strict=True)
    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].location == position
    assert f"{REF}@{DIGEST}" in diagnostics[0].message


def test_tag_platform_and_mirror_observations_can_resolve_references():
    """Direct registry discovery/acquisition is evidence, not a dangling reference itself."""
    records = [
        {
            "kind": "ArtifactMirrored",
            "from": OCCURRENCE,
            "to": {**OCCURRENCE, "digest": OTHER},
        },
        {
            "kind": "ImageIndexObserved",
            "occurrence": OCCURRENCE,
            "index": {"digest": DIGEST},
            "platforms": [{"digest": OTHER}],
        },
        tag("2026-10-28T00:00:00Z"),
        deployed(),
    ]
    assert (
        reference_diagnostics(
            [(Path(str(index)), record) for index, record in enumerate(records)]
        )
        == []
    )


def test_references_are_repository_scoped_not_just_digest_scoped():
    """The same content observed in a different repository cannot resolve a reference."""
    other_repo = observed()
    other_repo["occurrence"] = {**OCCURRENCE, "repository": "example/different"}
    assert (
        len(reference_diagnostics([(Path("o"), other_repo), (Path("d"), deployed())]))
        == 1
    )


def test_cli_warning_and_json_strict_validation(tmp_path: Path):
    """Permissive indexing is visibly warned; strict validate returns structured errors."""
    root = tmp_path / "input"
    root.mkdir()
    (root / "deploy.json").write_text(json.dumps(deployed()))
    runner = CliRunner()
    warning = runner.invoke(
        cli,
        [
            "index",
            str(root),
            "-d",
            str(tmp_path / "db"),
            "--schema-dir",
            str(SCHEMAS),
        ],
    )
    assert (
        warning.exit_code == 0
        and "warning:" in warning.output
        and "$.image" in warning.output
    )
    strict = runner.invoke(
        cli,
        [
            "validate",
            str(root),
            "--schema-dir",
            str(SCHEMAS),
            "--strict-references",
            "--format",
            "json",
        ],
    )
    assert strict.exit_code == 1
    body = json.loads(strict.output)
    assert body["errorCount"] == 1 and body["diagnostics"][0]["severity"] == "error"


def test_cli_deployment_history_and_tag_json(tmp_path: Path):
    """CLI commands expose the same additive history/interval fields as shared queries."""
    database = tmp_path / "db"
    with GraphStore(database) as graph:
        graph.init_schema()
        Indexer(graph).index_records(
            [deployed(), deployed(version="2"), tag("2026-10-28T00:00:00Z")]
        )
    runner = CliRunner()
    deployments = runner.invoke(
        cli, ["deployments", "--ref", REF, "-d", str(database), "--format", "json"]
    )
    assert deployments.exit_code == 0
    assert len(json.loads(deployments.output)) == 2
    tags = runner.invoke(
        cli,
        [
            "tag-history",
            "--repo",
            REF,
            "--tag",
            "stable",
            "-d",
            str(database),
            "--format",
            "json",
        ],
    )
    assert tags.exit_code == 0
    assert json.loads(tags.output)[0]["validFrom"] == "2026-10-28T00:00:00Z"


def test_old_schema_is_rejected_with_rebuild_guidance(tmp_path: Path):
    """Old derived databases are not silently migrated or stripped of deployment facts."""
    with GraphStore(tmp_path / "old") as graph:
        graph.execute("CREATE NODE TABLE Occurrence(key STRING, PRIMARY KEY(key))")
        graph.execute("CREATE NODE TABLE Deployment(key STRING, PRIMARY KEY(key))")
        graph.execute(
            "CREATE REL TABLE RUNS(FROM Deployment TO Occurrence, recordedAt STRING)"
        )
        with pytest.raises(ValueError, match="index --rebuild"):
            graph.init_schema()
        assert not any(
            row["name"] == "eventId"
            for row in graph.query("CALL table_info('RUNS') RETURN name")
        )


@pytest.mark.parametrize("command", ["show", "deployments", "index"])
def test_legacy_read_commands_return_rebuild_guidance(tmp_path: Path, command: str):
    """Query and index CLI opens turn legacy-schema rejection into actionable Click errors."""
    database = tmp_path / "old"
    with GraphStore(database) as graph:
        graph.execute("CREATE NODE TABLE Occurrence(key STRING, PRIMARY KEY(key))")
        graph.execute("CREATE NODE TABLE Deployment(key STRING, PRIMARY KEY(key))")
        graph.execute(
            "CREATE REL TABLE RUNS(FROM Deployment TO Occurrence, recordedAt STRING)"
        )
    if command == "index":
        root = tmp_path / "input"
        root.mkdir()
        (root / "observed.json").write_text(json.dumps(observed()))
        args = ["index", str(root), "--schema-dir", str(SCHEMAS), "-d", str(database)]
    else:
        args = [command, "--ref", f"{REF}@{DIGEST}", "-d", str(database)]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1
    assert "cssc-graph index --rebuild" in result.output
    assert "Binder exception" not in result.output
    assert result.exception is not None and isinstance(result.exception, SystemExit)


def test_tag_target_can_revert_and_intervals_stay_separate(store: GraphStore):
    """Returning to an old digest creates a new window, not a fabricated continuous one."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T00:00:00Z"),
            tag("2026-10-28T01:00:00Z", OTHER),
            tag("2026-10-28T02:00:00Z"),
        ]
    )
    history = queries.tag_history(store, REF, "stable")
    assert history[0]["validUntil"] == history[1]["validFrom"] == "2026-10-28T01:00:00Z"
    assert history[-1]["validFrom"] == "2026-10-28T02:00:00Z"
    shown = queries.show(store, f"{REF}@{DIGEST}")
    assert len(shown["tags"]) == 2
    assert shown["tags"][0]["validFrom"] != shown["tags"][1]["validFrom"]


def test_deployment_history_sorts_offsets_and_is_environment_scoped(store: GraphStore):
    """Event ordering uses real instants while keeping environment identity attached."""
    later = deployed("2026-10-28T00:30:00Z")
    earlier = deployed("2026-10-28T01:00:00+01:00")
    later["environment"] = {"cluster": "another", "namespace": "demo"}
    Indexer(store).index_records([later, earlier])
    history = queries.deployment_history(store, REF)
    assert [row["cluster"] for row in history] == ["test", "another"]


def test_equivalent_offsets_with_one_target_are_not_ambiguous(store: GraphStore):
    """Multiple spellings of the same instant are compatible when their digest agrees."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T01:00:00+01:00"),
            tag("2026-10-28T00:00:00Z"),
        ]
    )
    rows = queries.tag_history(store, REF, "stable")
    assert len(rows) == 2 and not any(row["ambiguous"] for row in rows)
    assert queries.resolve_seed(store, ref=f"{REF}:stable") == [f"{REF}@{DIGEST}"]


def test_later_unambiguous_tag_observation_resolves_after_a_conflict(store: GraphStore):
    """A past conflict remains visible without blocking an independently known later target."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T00:00:00Z"),
            tag("2026-10-28T00:00:00Z", OTHER),
            tag("2026-10-28T01:00:00Z", OTHER),
        ]
    )
    rows = queries.tag_history(store, REF, "stable")
    assert rows[-1]["validFrom"] == "2026-10-28T01:00:00Z"
    assert queries.resolve_seed(store, ref=f"{REF}:stable") == [f"{REF}@{OTHER}"]


def test_strict_success_and_unknown_query_shapes(store: GraphStore, tmp_path: Path):
    """Strict indexing succeeds with complete evidence, and unknown histories remain empty."""
    root = tmp_path / "input"
    root.mkdir()
    for name, record in (("a-deploy", deployed()), ("z-observed", observed())):
        (root / f"{name}.json").write_text(json.dumps(record))
    stats = index_data(store, root, SCHEMAS, strict_references=True)
    assert stats.records == 2 and stats.diagnostics == []
    assert queries.tag_history(store, REF, "absent") == []
    assert queries.deployment_history(store, "ghcr.io/example/absent") == []


def test_show_keeps_tag_observations_chronological_across_tag_names(store: GraphStore):
    """Artifact details retain chronological ordering rather than grouping by tag name."""
    earlier = {**tag("2026-10-28T00:00:00Z"), "tag": "z-first"}
    later = {**tag("2026-10-28T01:00:00Z"), "tag": "a-second"}
    Indexer(store).index_records([later, earlier])
    assert [row["tag"] for row in queries.show(store, f"{REF}@{DIGEST}")["tags"]] == [
        "z-first",
        "a-second",
    ]


def test_schema_valid_lowercase_utc_timestamp_is_supported(store: GraphStore):
    """RFC 3339 permits lowercase t/z even though datetime rejects lowercase z."""
    Indexer(store).index_record(tag("2026-10-28t00:00:00z"))
    assert (
        queries.tag_history(store, REF, "stable")[0]["validFrom"]
        == "2026-10-28T00:00:00Z"
    )


def test_schema_valid_leap_second_stays_between_adjacent_seconds(store: GraphStore):
    """A leap second is neither rejected nor collapsed into the next minute."""
    Indexer(store).index_records(
        [
            tag("2027-01-01T00:00:00Z"),
            tag("2026-12-31T23:59:60Z", OTHER),
            tag("2026-12-31T23:59:59.999999999Z"),
        ]
    )
    rows = queries.tag_history(store, REF, "stable")
    assert [row["digest"] for row in rows] == [DIGEST, OTHER, DIGEST]
    assert rows[0]["validUntil"] == rows[1]["validFrom"] == "2026-12-31T23:59:60Z"
    assert rows[1]["validUntil"] == "2027-01-01T00:00:00Z"


def test_deployments_preserve_sub_microsecond_order(store: GraphStore):
    """Deployment ordering follows exact instants rather than truncated event-ID ties."""
    Indexer(store).index_records(
        [
            deployed("2026-10-28T00:00:00.0000002Z", version="later"),
            deployed("2026-10-28t00:00:00.0000001z", version="earlier"),
        ]
    )
    assert [row["chartVersion"] for row in queries.deployment_history(store, REF)] == [
        "earlier",
        "later",
    ]


def test_sub_microsecond_instants_do_not_become_a_false_conflict(store: GraphStore):
    """Datetime truncation must not collapse two distinct schema-valid observations."""
    Indexer(store).index_records(
        [
            tag("2026-10-28T00:00:00.0000002Z", OTHER),
            tag("2026-10-28T01:00:00.0000001+01:00"),
        ]
    )
    rows = queries.tag_history(store, REF, "stable")
    assert not any(row["ambiguous"] for row in rows)
    assert rows[0]["validFrom"] == "2026-10-28T00:00:00.0000001Z"
    assert (
        rows[0]["validUntil"] == rows[1]["validFrom"] == "2026-10-28T00:00:00.0000002Z"
    )
    assert queries.resolve_seed(store, ref=f"{REF}:stable") == [f"{REF}@{OTHER}"]
