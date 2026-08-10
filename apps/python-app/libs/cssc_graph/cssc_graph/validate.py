"""Validate supply-chain-graph data files against the JSON Schemas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import yamlio
from .identity import content_id
from .schema import SchemaBundle, load_schemas

SOURCES_FILENAME = "sources.yaml"
_RECORD_SUFFIXES = {".yaml", ".yml", ".json"}


@dataclass(frozen=True)
class Diagnostic:
    """A single validation problem, addressed to a file and a location."""

    file: Path
    location: str
    message: str
    severity: str = "error"

    def format(self, root: Path | None = None) -> str:
        shown = self.file
        if root is not None:
            try:
                shown = self.file.relative_to(root)
            except ValueError:
                shown = self.file
        return f"{self.severity}: {shown}: {self.location}: {self.message}"


def default_schema_dir(root: Path) -> Path:
    return Path(root) / "schema"


def discover_record_files(root: Path, schema_dir: Path) -> list[Path]:
    """All data files under *root* to validate, excluding the schema directory."""

    root = Path(root)
    schema_dir = Path(schema_dir).resolve()
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in _RECORD_SUFFIXES:
            continue
        if schema_dir in path.resolve().parents or path.resolve() == schema_dir:
            continue
        files.append(path)
    return files


def _load_yaml(path: Path) -> tuple[Any, Diagnostic | None]:
    try:
        return yamlio.load(path.read_text(encoding="utf-8")), None
    except yaml.YAMLError as exc:
        return None, Diagnostic(path, "<file>", f"YAML parse error: {exc}")


def validate_file(path: Path, bundle: SchemaBundle) -> list[Diagnostic]:
    """Validate a single data file; returns an empty list when it is valid."""

    data, parse_error = _load_yaml(path)
    if parse_error is not None:
        return [parse_error]
    if data is None:
        return [Diagnostic(path, "<file>", "file is empty")]

    if path.name == SOURCES_FILENAME:
        if bundle.sources_schema is None:
            return [Diagnostic(path, "<file>", "no sources schema is available")]
        return _apply_schema(path, data, bundle, bundle.sources_schema)

    if not isinstance(data, dict):
        return [Diagnostic(path, "<file>", "expected a single record mapping")]

    kind = data.get("kind")
    if not kind:
        return [Diagnostic(path, "$.kind", "record is missing 'kind'")]
    schema = bundle.by_kind.get(kind)
    if schema is None:
        known = ", ".join(sorted(bundle.by_kind)) or "(none)"
        return [Diagnostic(path, "$.kind", f"unknown kind '{kind}'; known kinds: {known}")]

    diagnostics = _apply_schema(path, data, bundle, schema)

    stated_id = data.get("id")
    if stated_id:
        computed = content_id(data)
        if stated_id != computed:
            diagnostics.append(
                Diagnostic(
                    path,
                    "$.id",
                    f"id does not match content hash (stated {stated_id}, computed {computed})",
                )
            )
    return diagnostics


def _apply_schema(
    path: Path, data: Any, bundle: SchemaBundle, schema: dict[str, Any]
) -> list[Diagnostic]:
    validator = bundle.validator_for(schema)
    diagnostics: list[Diagnostic] = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        diagnostics.append(Diagnostic(path, error.json_path, error.message))
    return diagnostics


def validate_data(root: Path, schema_dir: Path | None = None) -> list[Diagnostic]:
    """Validate every record under *root*. Returns all diagnostics found."""

    root = Path(root)
    schema_dir = Path(schema_dir) if schema_dir is not None else default_schema_dir(root)
    bundle = load_schemas(schema_dir)

    diagnostics: list[Diagnostic] = []
    for path in discover_record_files(root, schema_dir):
        diagnostics.extend(validate_file(path, bundle))
    return diagnostics
