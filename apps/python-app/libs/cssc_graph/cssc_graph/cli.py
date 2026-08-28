"""``cssc-graph`` command line interface (Python Click).

Phase 1 ships ``validate`` (schema-check the data files) and ``id`` (print a
record's deterministic content id). Later phases add ``index`` and the query
commands, sharing the same underlying functions with the graph service.
"""

from __future__ import annotations

import json
import re
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

# Cypher clauses that would mutate the graph; the read-only `cypher` command rejects them.
_CYPHER_WRITE = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|DROP|ALTER|COPY|REMOVE|INSERT|LOAD)\b",
    re.IGNORECASE,
)


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


# -- query commands (read-only) ----------------------------------------------


def _database_option(func):
    return click.option(
        "--database",
        "-d",
        type=click.Path(exists=True, path_type=Path),
        default=DEFAULT_DATABASE,
        help="LadybugDB database directory (default: .graph).",
    )(func)


def _format_option(func):
    return click.option(
        "--format",
        "output_format",
        type=click.Choice(["text", "json"]),
        default="text",
        help="Output format.",
    )(func)


def _open_store(database: Path):
    from .graph import GraphStore

    return GraphStore(database).connect()


def _emit_subgraph(subgraph: dict, output_format: str) -> None:
    if output_format == "json":
        click.echo(json.dumps(subgraph, indent=2))
        return
    refs = {n["key"]: n.get("ref", n["key"]) for n in subgraph["nodes"]}
    click.echo(f"{len(subgraph['nodes'])} node(s), {len(subgraph['edges'])} edge(s):")
    for edge in subgraph["edges"]:
        tag = f" ({edge['tag']})" if edge.get("tag") else ""
        atype = f" [{edge['artifactType']}]" if edge.get("artifactType") else ""
        plat = f" {{{edge['platform']}}}" if edge.get("platform") else ""
        frm = refs.get(edge["from"], edge["from"])
        to = refs.get(edge["to"], edge["to"])
        click.echo(f"  {frm}  --{edge['type']}-->  {to}{tag}{atype}{plat}")


@cli.command()
@_database_option
@click.option("--digest", help="Seed by artifact digest (sha256:...).")
@click.option("--ref", help="Seed by registry/repository[@digest|:tag].")
@click.option("--depth", default=6, show_default=True, help="Max traversal depth.")
@_format_option
def path(database: Path, digest: str | None, ref: str | None, depth: int, output_format: str) -> None:
    """Show the supply-chain path of an artifact (upstream and downstream)."""

    if not digest and not ref:
        raise click.UsageError("provide --digest or --ref")
    from . import queries

    store = _open_store(database)
    try:
        subgraph = queries.path(store, digest=digest, ref=ref, depth=depth)
    finally:
        store.close()
    _emit_subgraph(subgraph, output_format)


@cli.command(name="tag-history")
@_database_option
@click.option("--repo", required=True, help="Fully-qualified registry/repository.")
@click.option("--tag", required=True)
@_format_option
def tag_history(database: Path, repo: str, tag: str, output_format: str) -> None:
    """List every digest a tag pointed to over time, chronologically."""

    from . import queries

    store = _open_store(database)
    try:
        history = queries.tag_history(store, repo, tag)
    finally:
        store.close()
    if output_format == "json":
        click.echo(json.dumps(history, indent=2))
        return
    for entry in history:
        click.echo(f"  {entry['observedAt']}  {entry['digest']}  {entry.get('runUrl', '')}".rstrip())
    click.echo(f"{len(history)} observation(s).")


@cli.command()
@_database_option
@click.option("--ref", required=True, help="The built image (registry/repository[@digest|:tag]).")
@click.option("--depth", default=10, show_default=True)
@_format_option
def bases(database: Path, ref: str, depth: int, output_format: str) -> None:
    """Show the direct and transitive base images of a built image."""

    from . import queries

    store = _open_store(database)
    try:
        subgraph = queries.bases(store, ref, depth=depth)
    finally:
        store.close()
    _emit_subgraph(subgraph, output_format)


@cli.command()
@_database_option
@click.option("--base", required=True, help="The base image (registry/repository[@digest|:tag]).")
@click.option("--depth", default=10, show_default=True)
@_format_option
def derived(database: Path, base: str, depth: int, output_format: str) -> None:
    """Show images built (transitively) from a base image."""

    from . import queries

    store = _open_store(database)
    try:
        subgraph = queries.derived(store, base, depth=depth)
    finally:
        store.close()
    _emit_subgraph(subgraph, output_format)


@cli.command()
@_database_option
@click.option("--digest", help="Seed by artifact digest (sha256:...).")
@click.option("--ref", help="Seed by registry/repository[@digest|:tag].")
@click.option("--depth", default=3, show_default=True, help="Max referrer depth (referrers-of-referrers).")
@click.option(
    "--rollup/--no-rollup",
    default=True,
    show_default=True,
    help="Roll per-platform child referrers up onto a multi-arch index; --no-rollup keeps them on the child manifests.",
)
@_format_option
def referrers(database: Path, digest: str | None, ref: str | None, depth: int, rollup: bool, output_format: str) -> None:
    """List the referrer artifacts (SBOM/provenance/VEX/signatures) attached to an image."""

    if not digest and not ref:
        raise click.UsageError("provide --digest or --ref")
    from . import queries

    store = _open_store(database)
    try:
        subgraph = queries.referrers(store, digest=digest, ref=ref, depth=depth, rollup=rollup)
    finally:
        store.close()
    _emit_subgraph(subgraph, output_format)


@cli.command()
@_database_option
@click.option("--annotation", help="Filter by annotation name=value.")
@click.option("--type", "artifact_type", help="Filter by artifact/media type.")
@click.option("--ref", help="Filter by registry/repository.")
@_format_option
def find(database: Path, annotation: str | None, artifact_type: str | None, ref: str | None, output_format: str) -> None:
    """Find occurrences by annotation, artifact type, or repository."""

    if not any((annotation, artifact_type, ref)):
        raise click.UsageError("provide --annotation, --type, or --ref")
    from . import queries

    store = _open_store(database)
    try:
        results = queries.find(store, annotation=annotation, artifact_type=artifact_type, ref=ref)
    except ValueError as exc:
        raise click.UsageError(str(exc))
    finally:
        store.close()
    if output_format == "json":
        click.echo(json.dumps(results, indent=2))
        return
    for row in results:
        click.echo(f"  {row['ref']}  {row['digest']}")
    click.echo(f"{len(results)} match(es).")


@cli.command()
@_database_option
@click.option("--ref", required=True, help="Occurrence (registry/repository[@digest|:tag]).")
@_format_option
def show(database: Path, ref: str, output_format: str) -> None:
    """Show an occurrence's details, annotations, tags, and nearby path."""

    if "@" not in ref and ":" not in ref.rpartition("/")[2]:
        raise click.UsageError(
            "provide a specific occurrence: registry/repository@digest or registry/repository:tag"
        )
    from . import queries

    store = _open_store(database)
    try:
        data = queries.show(store, ref)
    finally:
        store.close()
    if data is None:
        raise click.ClickException(f"no occurrence found for {ref!r}")
    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
        return
    occ = data["occurrence"]
    click.echo(f"occurrence: {occ['key']}")
    if data.get("deleted"):
        reason = occ.get("deleteReason") or "unknown"
        click.echo(f"  deleted: {occ.get('deletedAt')} (reason: {reason})")
    if data["artifact"]:
        art = data["artifact"]
        click.echo(f"  type: {art.get('artifactType') or art.get('mediaType') or '-'}")
    for ann in data["annotations"]:
        click.echo(f"  annotation: {ann['name']}={ann['value']}")
    for tag in data["tags"]:
        click.echo(f"  tag: {tag['tag']} @ {tag['observedAt']}")
    for r in data.get("referrers", []):
        plat = f" {{{r['platform']}}}" if r.get("platform") else ""
        click.echo(f"  referrer: {r.get('artifactType') or '-'} ({r['from']}){plat}")


@cli.command()
@_database_option
@click.option("--digest", help="Seed by artifact digest.")
@click.option("--ref", help="Seed by registry/repository[@digest|:tag].")
@click.option("--depth", default=3, show_default=True)
@click.option(
    "--format",
    "export_format",
    type=click.Choice(["cytoscape", "mermaid", "json"]),
    default="cytoscape",
    show_default=True,
)
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Write to a file.")
def export(database: Path, digest: str | None, ref: str | None, depth: int, export_format: str, output: Path | None) -> None:
    """Export a bounded subgraph for offline visualization."""

    if not digest and not ref:
        raise click.UsageError("provide --digest or --ref")
    from . import queries

    store = _open_store(database)
    try:
        subgraph = queries.path(store, digest=digest, ref=ref, depth=depth)
    finally:
        store.close()

    if export_format == "cytoscape":
        text = json.dumps(queries.to_cytoscape(subgraph), indent=2)
    elif export_format == "mermaid":
        text = queries.to_mermaid(subgraph)
    else:
        text = json.dumps(subgraph, indent=2)

    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"Wrote {export_format} to {output}.")
    else:
        click.echo(text)


@cli.command()
@_database_option
@_format_option
@click.argument("query", nargs=-1, required=True)
def cypher(database: Path, output_format: str, query: tuple[str, ...]) -> None:
    """Run a read-only Cypher QUERY and print the rows.

    Multi-word queries need no quoting; write clauses are rejected.
    """

    text = " ".join(query)
    if _CYPHER_WRITE.search(text):
        raise click.UsageError("cypher is read-only; write clauses are not allowed")
    store = _open_store(database)
    try:
        rows = store.query(text)
    finally:
        store.close()
    if output_format == "json":
        click.echo(json.dumps(rows, indent=2))
        return
    for row in rows:
        click.echo("  " + "  ".join(f"{k}={v}" for k, v in row.items()))
    click.echo(f"{len(rows)} row(s).")


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
