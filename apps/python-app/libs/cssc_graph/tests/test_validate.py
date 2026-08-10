from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from cssc_graph.cli import cli
from cssc_graph.identity import content_id
from cssc_graph.validate import validate_data

REPO_ROOT = Path(__file__).resolve().parents[5]
DATA_ROOT = REPO_ROOT / "supply-chain-graph"
SCHEMA_DIR = DATA_ROOT / "schema"

pytestmark = pytest.mark.skipif(
    not SCHEMA_DIR.exists(), reason="repository data root not present"
)


def _valid_mirrored() -> dict:
    digest = "sha256:" + "2" * 64
    return {
        "schemaVersion": 1,
        "kind": "ArtifactMirrored",
        "recordedAt": "2026-08-09T12:15:00Z",
        "source": {"type": "github-actions", "runUrl": "https://example/runs/1"},
        "from": {"registry": "docker.io", "repository": "library/python", "digest": digest},
        "to": {"registry": "ghcr.io", "repository": "toddysm/quarantine/python", "digest": digest},
        "tag": "3.14-slim",
    }


def _write(tmp: Path, name: str, record: dict) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / name
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


# --- the committed data validates cleanly -----------------------------------


def test_repository_data_root_is_valid():
    assert validate_data(DATA_ROOT) == []


def test_examples_directory_is_valid():
    diagnostics = validate_data(DATA_ROOT / "examples", schema_dir=SCHEMA_DIR)
    assert diagnostics == []


# --- malformed records produce actionable diagnostics -----------------------


def test_missing_required_field(tmp_path: Path):
    record = _valid_mirrored()
    del record["tag"]
    _write(tmp_path, "bad.yaml", record)
    diagnostics = validate_data(tmp_path, schema_dir=SCHEMA_DIR)
    assert any("tag" in d.message for d in diagnostics)


def test_unknown_kind(tmp_path: Path):
    _write(tmp_path, "bad.yaml", {**_valid_mirrored(), "kind": "Nope"})
    diagnostics = validate_data(tmp_path, schema_dir=SCHEMA_DIR)
    assert any("unknown kind" in d.message for d in diagnostics)


def test_bad_digest_rejected(tmp_path: Path):
    record = _valid_mirrored()
    record["to"]["digest"] = "not-a-digest"
    _write(tmp_path, "bad.yaml", record)
    diagnostics = validate_data(tmp_path, schema_dir=SCHEMA_DIR)
    assert diagnostics, "expected a digest pattern violation"


def test_registry_with_slash_rejected(tmp_path: Path):
    record = _valid_mirrored()
    record["to"]["registry"] = "ghcr.io/toddysm"  # registry must not contain '/'
    _write(tmp_path, "bad.yaml", record)
    diagnostics = validate_data(tmp_path, schema_dir=SCHEMA_DIR)
    assert diagnostics, "expected a registry pattern violation"


def test_additional_property_rejected(tmp_path: Path):
    _write(tmp_path, "bad.yaml", {**_valid_mirrored(), "bogus": True})
    diagnostics = validate_data(tmp_path, schema_dir=SCHEMA_DIR)
    assert diagnostics, "unexpected top-level property should fail closed schema"


# --- content-id idempotency check -------------------------------------------


def test_id_mismatch_is_flagged(tmp_path: Path):
    record = {**_valid_mirrored(), "id": "sha256:" + "0" * 64}
    _write(tmp_path, "bad.yaml", record)
    diagnostics = validate_data(tmp_path, schema_dir=SCHEMA_DIR)
    assert any(d.location == "$.id" for d in diagnostics)


def test_correct_id_passes(tmp_path: Path):
    record = _valid_mirrored()
    record["id"] = content_id(record)
    _write(tmp_path, "ok.yaml", record)
    assert validate_data(tmp_path, schema_dir=SCHEMA_DIR) == []


# --- CLI wiring --------------------------------------------------------------


def test_cli_validate_examples_exit_zero():
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(DATA_ROOT / "examples"), "--schema-dir", str(SCHEMA_DIR)])
    assert result.exit_code == 0, result.output


def test_cli_validate_invalid_exit_one(tmp_path: Path):
    _write(tmp_path, "bad.yaml", {**_valid_mirrored(), "kind": "Nope"})
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(tmp_path), "--schema-dir", str(SCHEMA_DIR)])
    assert result.exit_code == 1
    assert "unknown kind" in result.output


def test_cli_id_matches_identity():
    runner = CliRunner()
    example = DATA_ROOT / "examples" / "artifact-mirrored.yaml"
    result = runner.invoke(cli, ["id", str(example)])
    assert result.exit_code == 0
    expected = content_id(yaml.safe_load(example.read_text(encoding="utf-8")))
    assert result.output.strip() == expected
