"""Load the JSON Schemas and build validators with cross-file ``$ref`` support."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMA_GLOB = "*.schema.json"
SOURCES_SCHEMA_TITLE = "Sources"


@dataclass(frozen=True)
class SchemaBundle:
    """Loaded schemas plus a resolver registry for ``$ref`` between them."""

    registry: Registry
    by_kind: dict[str, dict[str, Any]]
    sources_schema: dict[str, Any] | None

    def validator_for(self, schema: dict[str, Any]) -> Draft202012Validator:
        return Draft202012Validator(
            schema,
            registry=self.registry,
            format_checker=FormatChecker(),
        )


def load_schemas(schema_dir: Path) -> SchemaBundle:
    """Load every ``*.schema.json`` in *schema_dir* into a resolvable bundle.

    Record schemas are indexed by the ``const`` value of their ``kind`` property;
    the sources schema is recognised by its title.
    """

    schema_dir = Path(schema_dir)
    files = sorted(schema_dir.glob(SCHEMA_GLOB))
    if not files:
        raise FileNotFoundError(f"no {SCHEMA_GLOB} schemas found in {schema_dir}")

    resources: list[tuple[str, Resource]] = []
    by_kind: dict[str, dict[str, Any]] = {}
    sources_schema: dict[str, Any] | None = None

    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        uri = schema.get("$id")
        if not uri:
            raise ValueError(f"{path} is missing a $id")
        resources.append((uri, Resource.from_contents(schema)))

        kind_const = (
            schema.get("properties", {}).get("kind", {}).get("const")
        )
        if kind_const:
            by_kind[kind_const] = schema
        elif schema.get("title") == SOURCES_SCHEMA_TITLE:
            sources_schema = schema

    registry = Registry().with_resources(resources)
    return SchemaBundle(registry=registry, by_kind=by_kind, sources_schema=sources_schema)
