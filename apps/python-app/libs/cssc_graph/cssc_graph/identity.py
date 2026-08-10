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
    return make_occurrence_key(registry, repository, digest)


def make_occurrence_key(registry: str, repository: str, digest: str) -> str:
    """Build the fully-qualified occurrence key from its parts."""

    return f"{registry}/{repository}@{digest}"


def make_ref(registry: str, repository: str) -> str:
    """The registry + repository name without a digest, e.g. ghcr.io/owner/img."""

    return f"{registry}/{repository}"


def tag_key(registry: str, repository: str, tag: str) -> str:
    """Stable key for a tag in a repository: ``registry/repository:tag``."""

    return f"{registry}/{repository}:{tag}"


def split_ref(name: str) -> tuple[str, str]:
    """Split a fully-qualified image name into ``(registry, repository)``.

    The registry is the first path component (it carries the login server, e.g.
    ``ghcr.io`` or ``first.registry.io``); the rest is the repository.
    """

    if "/" not in name:
        raise ValueError(f"not a fully-qualified name (missing registry): {name!r}")
    registry, repository = name.split("/", 1)
    if not registry or not repository:
        raise ValueError(f"not a fully-qualified name: {name!r}")
    return registry, repository
