"""Diagnose references without independent occurrence evidence in the input set."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from .identity import make_occurrence_key, occurrence_key, split_ref
from .validate import Diagnostic


class UnresolvedReferences(ValueError):
    """Reject strict indexing while preserving the individual file diagnostics."""

    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__(
            f"{len(diagnostics)} unresolved occurrence reference(s); nothing indexed."
        )


def _facts(record: Mapping[str, Any]) -> tuple[set[str], list[tuple[str, str]]]:
    """Separate direct observations from reference-only positions of a validated record."""
    kind = record["kind"]
    declared: set[str] = set()
    references: list[tuple[str, str]] = []
    if kind == "ArtifactObserved":
        declared.add(occurrence_key(record["occurrence"]))
    elif kind == "ArtifactMirrored":
        # A successful copy directly observes both the upstream and acquired image.
        declared.update(occurrence_key(record[side]) for side in ("from", "to"))
    elif kind == "ArtifactPromoted":
        declared.add(occurrence_key(record["to"]))
        references.append(("$.from", occurrence_key(record["from"])))
    elif kind == "ArtifactBuilt":
        declared.add(occurrence_key(record["image"]))
        base = record["base"]
        registry, repository = split_ref(base["name"])
        references.append(
            ("$.base", make_occurrence_key(registry, repository, base["digest"]))
        )
    elif kind == "ArtifactDeployed":
        references.append(("$.image", occurrence_key(record["image"])))
    elif kind in {
        "TagObserved",
        "ArtifactDeleted",
        "ReferrerObserved",
        "ImageIndexObserved",
    }:
        occurrence = record["occurrence"]
        registry, repository = occurrence["registry"], occurrence["repository"]
        if kind == "TagObserved":
            declared.add(make_occurrence_key(registry, repository, record["digest"]))
        elif kind == "ArtifactDeleted":
            references.append(
                (
                    "$.digest",
                    make_occurrence_key(registry, repository, record["digest"]),
                )
            )
        elif kind == "ReferrerObserved":
            declared.add(
                make_occurrence_key(registry, repository, record["referrer"]["digest"])
            )
            references.append(
                (
                    "$.subject",
                    make_occurrence_key(
                        registry, repository, record["subject"]["digest"]
                    ),
                )
            )
        else:
            declared.add(
                make_occurrence_key(registry, repository, record["index"]["digest"])
            )
            declared.update(
                make_occurrence_key(registry, repository, child["digest"])
                for child in record["platforms"]
            )
    return declared, references


def reference_diagnostics(
    records: Iterable[tuple[Path, Mapping[str, Any]]],
    *,
    strict: bool = False,
) -> list[Diagnostic]:
    """Check all records together, not file order, without mutating a graph.

    Missing evidence in this input set is a warning by default, not proof that
    the remote artifact never existed. Strict mode returns error diagnostics.
    """
    declared: set[str] = set()
    references: list[tuple[Path, str, str]] = []
    for path, record in records:
        observations, targets = _facts(record)
        declared.update(observations)
        references.extend((path, location, key) for location, key in targets)
    return [
        Diagnostic(
            path,
            location,
            f"unresolved occurrence {key}: add an observation/acquisition/build record "
            "or include the missing evidence in the data root",
            severity="error" if strict else "warning",
        )
        for path, location, key in references
        if key not in declared
    ]
