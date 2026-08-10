from __future__ import annotations

from cssc_graph.identity import (
    canonical_json,
    content_id,
    occurrence_key,
    semantic_payload,
)

BASE_RECORD = {
    "schemaVersion": 1,
    "kind": "ArtifactMirrored",
    "recordedAt": "2026-08-09T12:15:00Z",
    "source": {"type": "github-actions", "runUrl": "https://example/runs/1"},
    "from": {
        "registry": "docker.io",
        "repository": "library/python",
        "digest": "sha256:" + "2" * 64,
    },
    "to": {
        "registry": "ghcr.io",
        "repository": "toddysm/quarantine/python",
        "digest": "sha256:" + "2" * 64,
    },
    "tag": "3.14-slim",
}


def test_canonical_json_is_key_order_independent():
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b == '{"a":2,"b":1}'


def test_semantic_payload_drops_volatile_fields():
    payload = semantic_payload({**BASE_RECORD, "id": "sha256:" + "0" * 64})
    assert "id" not in payload
    assert "recordedAt" not in payload
    assert "source" not in payload
    assert payload["kind"] == "ArtifactMirrored"


def test_content_id_ignores_volatile_fields():
    base_id = content_id(BASE_RECORD)
    changed = {
        **BASE_RECORD,
        "recordedAt": "2099-01-01T00:00:00Z",
        "source": {"type": "human"},
        "id": "sha256:" + "f" * 64,
    }
    assert content_id(changed) == base_id


def test_content_id_changes_with_semantic_change():
    other = {**BASE_RECORD, "tag": "3.13-slim"}
    assert content_id(other) != content_id(BASE_RECORD)


def test_content_id_is_sha256_prefixed():
    value = content_id(BASE_RECORD)
    assert value.startswith("sha256:")
    assert len(value) == len("sha256:") + 64


def test_occurrence_key_is_fully_qualified():
    first = occurrence_key(
        {"registry": "first.registry.io", "repository": "quarantine/python", "digest": "sha256:" + "2" * 64}
    )
    second = occurrence_key(
        {"registry": "second.registry.io", "repository": "quarantine/python", "digest": "sha256:" + "2" * 64}
    )
    # Same digest + repository, different registry → distinct occurrences.
    assert first != second
    assert first == "first.registry.io/quarantine/python@sha256:" + "2" * 64
