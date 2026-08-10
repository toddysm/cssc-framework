"""``cssc-graph`` command line interface (Python Click).

Phase 1 ships ``validate`` (schema-check the data files) and ``id`` (print a
record's deterministic content id). Later phases add ``index`` and the query
commands, sharing the same underlying functions with the graph service.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from . import __version__, yamlio
from .identity import content_id
from .validate import (
    default_schema_dir,
    discover_record_files,
    validate_data,
)

DEFAULT_ROOT = "supply-chain-graph"
DEFAULT_DATABASE = ".graph"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="cssc-graph")
def cli() -> None:
    """File-backed supply-chain graph tooling."""


@cli.command()
@click.argument(
    "root",
    default=DEFAULT_ROOT,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--schema-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Schema directory (defaults to <root>/schema).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def validate(root: Path, schema_dir: Path | None, output_format: str) -> None:
    """Validate every record under ROOT against the JSON Schemas."""

    resolved_schema_dir = schema_dir or default_schema_dir(root)
    try:
        files = discover_record_files(root, resolved_schema_dir)
        diagnostics = validate_data(root, resolved_schema_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))

    if output_format == "json":
        payload = {
            "filesChecked": len(files),
            "errorCount": len(diagnostics),
            "diagnostics": [
                {
                    "file": str(d.file),
                    "location": d.location,
                    "message": d.message,
                    "severity": d.severity,
                }
                for d in diagnostics
            ],
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        for diag in diagnostics:
            click.echo(diag.format(root))
        summary = f"Checked {len(files)} file(s); {len(diagnostics)} error(s)."
        click.echo(summary, err=bool(diagnostics))

    if diagnostics:
        sys.exit(1)


@cli.command()
@click.argument(
    "root",
    default=DEFAULT_ROOT,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--database",
    "-d",
    type=click.Path(path_type=Path),
    default=DEFAULT_DATABASE,
    help="LadybugDB database directory (default: .graph).",
)
@click.option(
    "--schema-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Schema directory (defaults to <root>/schema).",
)
@click.option(
    "--rebuild",
    is_flag=True,
    help="Delete any existing database first for a clean rebuild.",
)
def index(root: Path, database: Path, schema_dir: Path | None, rebuild: bool) -> None:
    """Validate ROOT, then index its records into a LadybugDB graph."""

    resolved_schema_dir = schema_dir or default_schema_dir(root)
    try:
        diagnostics = validate_data(root, resolved_schema_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc))
    if diagnostics:
        for diag in diagnostics:
            click.echo(diag.format(root), err=True)
        raise click.ClickException(f"{len(diagnostics)} validation error(s); nothing indexed.")

    # Imported lazily so `validate` and `id` work without the native dependency.
    from .graph import GraphStore
    from .indexer import index_data

    if rebuild:
        GraphStore.destroy(database)
    with GraphStore(database) as store:
        store.init_schema()
        stats = index_data(store, root, resolved_schema_dir)

    click.echo(f"Indexed {stats.records} record(s) into {database}.")
    for kind, count in sorted(stats.by_kind.items()):
        click.echo(f"  {kind}: {count}")


@cli.command(name="id")
@click.argument(
    "record",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def record_id(record: Path) -> None:
    """Print the deterministic content id of a single RECORD file."""

    data = yamlio.load(record.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise click.ClickException("record must be a single mapping")
    click.echo(content_id(data))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
