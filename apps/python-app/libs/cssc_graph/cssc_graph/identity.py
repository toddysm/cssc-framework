"""Identity and idempotency helpers for supply-chain-graph records.

Two identities matter:

- **Occurrence key** — a fully-qualified ``registry/repository@digest``. The
  registry login server is part of the key, so the same digest in two registries
  is two occurrences, never one.
- **Content id** — a ``sha256:`` hash over a record's *semantic* payload
  (everything except the volatile envelope fields ``id``, ``recordedAt`` and
  ``source``). Recording the same fact twice yields the same id, which is what
  makes indexing idempotent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

# Envelope fields that do not contribute to a record's semantic identity.
_VOLATILE_FIELDS = ("id", "recordedAt", "source")


def canonical_json(value: Any) -> str:
    """Return a stable, canonical JSON encoding (sorted keys, no whitespace)."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def semantic_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    """The record without the volatile envelope fields."""

    return {k: v for k, v in record.items() if k not in _VOLATILE_FIELDS}


def content_id(record: Mapping[str, Any]) -> str:
    """Compute the deterministic ``sha256:`` content id of a record."""

    payload = canonical_json(semantic_payload(record)).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def occurrence_key(occurrence: Mapping[str, Any]) -> str:
    """Return ``registry/repository@digest`` for a fully-qualified occurrence."""

    try:
        registry = occurrence["registry"]
        repository = occurrence["repository"]
        digest = occurrence["digest"]
    except KeyError as exc:  # pragma: no cover - guarded by schema in practice
        raise ValueError(f"occurrence missing {exc.args[0]!r}") from exc
    return f"{registry}/{repository}@{digest}"
