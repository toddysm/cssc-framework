"""Read-side query layer over the graph.

These functions return plain, JSON-serializable Python structures so the CLI and
the future graph service share one implementation. Traversals are bounded.
"""

from __future__ import annotations

from typing import Any

from .graph import GraphStore
from .identity import split_ref, tag_key

# Relationship types that form an artifact's supply-chain path.
PATH_RELS: tuple[str, ...] = ("MIRRORED_FROM", "PROMOTED_FROM", "BUILT_FROM")
DEFAULT_DEPTH = 6

_OCC_RETURN = (
    "n.key AS key, n.registry AS registry, n.repository AS repository, "
    "n.digest AS digest, n.ref AS ref, n.deletedAt AS deletedAt, "
    "n.deleteReason AS deleteReason"
)


def get_occurrence(store: GraphStore, key: str) -> dict[str, Any] | None:
    rows = store.query(
        "MATCH (o:Occurrence {key: $k}) "
        "RETURN o.key AS key, o.registry AS registry, o.repository AS repository, "
        "o.digest AS digest, o.ref AS ref, o.deletedAt AS deletedAt, "
        "o.deleteReason AS deleteReason",
        {"k": key},
    )
    return rows[0] if rows else None


def occurrences_for_digest(store: GraphStore, digest: str) -> list[dict[str, Any]]:
    return store.query(
        "MATCH (o:Occurrence {digest: $d}) "
        "RETURN o.key AS key, o.registry AS registry, o.repository AS repository, "
        "o.digest AS digest, o.ref AS ref ORDER BY o.key",
        {"d": digest},
    )


def resolve_seed(store: GraphStore, *, digest: str | None = None, ref: str | None = None) -> list[str]:
    """Resolve a digest or a reference into occurrence keys."""

    if digest:
        return [o["key"] for o in occurrences_for_digest(store, digest)]
    if not ref:
        return []
    if "@" in ref:  # a full occurrence key registry/repository@digest
        return [ref] if get_occurrence(store, ref) else []
    name, _, maybe_tag = ref.rpartition("/")
    if ":" in maybe_tag:  # registry/repository:tag
        repo_tail, tag = maybe_tag.split(":", 1)
        full_ref = f"{name}/{repo_tail}"
        registry, repository = split_ref(full_ref)
        latest = _latest_tag_occurrence(store, registry, repository, tag)
        return [latest] if latest else []
    # bare registry/repository — every occurrence with that name
    return [o["key"] for o in store.query(
        "MATCH (o:Occurrence {ref: $ref}) RETURN o.key AS key ORDER BY o.key",
        {"ref": ref},
    )]


def _latest_tag_occurrence(store: GraphStore, registry: str, repository: str, tag: str) -> str | None:
    rows = store.query(
        "MATCH (t:Tag {key: $tk})-[e:POINTED_TO]->(o:Occurrence) "
        "RETURN o.key AS key ORDER BY e.observedAt DESC LIMIT 1",
        {"tk": tag_key(registry, repository, tag)},
    )
    return rows[0]["key"] if rows else None


def _neighbors(store: GraphStore, key: str, rel: str, outgoing: bool) -> list[dict[str, Any]]:
    if outgoing:
        pattern = f"(o:Occurrence {{key: $k}})-[e:{rel}]->(n:Occurrence)"
    else:
        pattern = f"(o:Occurrence {{key: $k}})<-[e:{rel}]-(n:Occurrence)"
    return store.query(f"MATCH {pattern} RETURN {_OCC_RETURN}, e.tag AS tag", {"k": key})


def traverse(
    store: GraphStore,
    seeds: list[str],
    rels: tuple[str, ...],
    direction: str = "both",
    max_depth: int = DEFAULT_DEPTH,
) -> dict[str, Any]:
    """Bounded BFS from *seeds* over *rels*; returns ``{nodes, edges}``."""

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    visited: set[str] = set()
    frontier = list(dict.fromkeys(seeds))
    # Seed nodes are included even at depth 0 so a query always shows its subjects.
    for seed in frontier:
        occ = get_occurrence(store, seed)
        if occ:
            nodes[seed] = occ

    for _ in range(max_depth):
        nxt: list[str] = []
        for key in frontier:
            if key in visited:
                continue
            visited.add(key)
            occ = get_occurrence(store, key)
            if occ:
                nodes[key] = occ
            for rel in rels:
                if direction in ("out", "both"):
                    for row in _neighbors(store, key, rel, outgoing=True):
                        _record_node(nodes, row)
                        _add_edge(edges, seen_edges, rel, key, row["key"], row.get("tag"))
                        nxt.append(row["key"])
                if direction in ("in", "both"):
                    for row in _neighbors(store, key, rel, outgoing=False):
                        _record_node(nodes, row)
                        _add_edge(edges, seen_edges, rel, row["key"], key, row.get("tag"))
                        nxt.append(row["key"])
        frontier = [k for k in nxt if k not in visited]
        if not frontier:
            break

    return {"nodes": list(nodes.values()), "edges": edges}


def _record_node(nodes: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    key = row["key"]
    if key not in nodes:
        nodes[key] = {
            "key": key,
            "registry": row["registry"],
            "repository": row["repository"],
            "digest": row["digest"],
            "ref": row["ref"],
            "deletedAt": row.get("deletedAt"),
            "deleteReason": row.get("deleteReason"),
        }


def _add_edge(edges, seen, rel, frm, to, tag) -> None:
    ekey = (rel, frm, to)
    if ekey in seen:
        return
    seen.add(ekey)
    edge = {"type": rel, "from": frm, "to": to}
    if tag:
        edge["tag"] = tag
    edges.append(edge)


# -- public query journeys ----------------------------------------------------


def path(store: GraphStore, *, digest: str | None = None, ref: str | None = None, depth: int = DEFAULT_DEPTH) -> dict[str, Any]:
    seeds = resolve_seed(store, digest=digest, ref=ref)
    return traverse(store, seeds, PATH_RELS, direction="both", max_depth=depth)


def bases(store: GraphStore, ref: str, depth: int = 10) -> dict[str, Any]:
    seeds = resolve_seed(store, ref=ref)
    return traverse(store, seeds, ("BUILT_FROM",), direction="out", max_depth=depth)


def derived(store: GraphStore, base: str, depth: int = 10) -> dict[str, Any]:
    seeds = resolve_seed(store, ref=base)
    return traverse(store, seeds, ("BUILT_FROM",), direction="in", max_depth=depth)


def referrers(
    store: GraphStore,
    *,
    digest: str | None = None,
    ref: str | None = None,
    depth: int = 3,
) -> dict[str, Any]:
    """Referrer artifacts of a subject occurrence.

    Returns ``{nodes, edges}`` where each ``REFERS_TO`` edge carries the
    ``artifactType``. Follows referrers-of-referrers up to *depth* levels (a
    signature on an SBOM, etc.); ``depth=0`` returns just the subject, matching
    :func:`traverse`.
    """

    seeds = resolve_seed(store, digest=digest, ref=ref)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    # Keyed like the indexer's REFERS_TO merge so distinct observations and
    # artifact types between the same pair are all kept, not collapsed.
    seen_edges: set[tuple[str, str, str | None, str | None]] = set()
    for seed in seeds:
        occ = get_occurrence(store, seed)
        if occ:
            nodes[seed] = occ

    visited: set[str] = set()
    frontier = list(dict.fromkeys(seeds))
    for _ in range(depth):
        nxt: list[str] = []
        for key in frontier:
            if key in visited:
                continue
            visited.add(key)
            rows = store.query(
                "MATCH (r:Occurrence)-[e:REFERS_TO]->(s:Occurrence {key: $k}) "
                "RETURN r.key AS key, r.registry AS registry, r.repository AS repository, "
                "r.digest AS digest, r.ref AS ref, r.deletedAt AS deletedAt, "
                "r.deleteReason AS deleteReason, e.artifactType AS artifactType, "
                "e.observedAt AS observedAt ORDER BY e.artifactType, r.key",
                {"k": key},
            )
            for row in rows:
                _record_node(nodes, row)
                atype = row.get("artifactType")
                observed = row.get("observedAt")
                ekey = (row["key"], key, atype, observed)
                if ekey not in seen_edges:
                    seen_edges.add(ekey)
                    edges.append(
                        {
                            "type": "REFERS_TO",
                            "from": row["key"],
                            "to": key,
                            "artifactType": atype,
                            "observedAt": observed,
                        }
                    )
                nxt.append(row["key"])
        frontier = [k for k in nxt if k not in visited]
        if not frontier:
            break

    return {"nodes": list(nodes.values()), "edges": edges}


def tag_history(store: GraphStore, ref: str, tag: str) -> list[dict[str, Any]]:
    registry, repository = split_ref(ref)
    return store.query(
        "MATCH (t:Tag {key: $tk})-[e:POINTED_TO]->(o:Occurrence) "
        "RETURN e.observedAt AS observedAt, o.digest AS digest, o.key AS occurrence, "
        "e.runUrl AS runUrl ORDER BY e.observedAt",
        {"tk": tag_key(registry, repository, tag)},
    )


def find(
    store: GraphStore,
    *,
    annotation: str | None = None,
    artifact_type: str | None = None,
    ref: str | None = None,
) -> list[dict[str, Any]]:
    if annotation:
        name, sep, value = annotation.partition("=")
        if not sep:
            raise ValueError("annotation filter must be name=value")
        return store.query(
            "MATCH (o:Occurrence)-[:HAS_ANNOTATION]->(a:Annotation {key: $k}) "
            "RETURN o.key AS key, o.ref AS ref, o.digest AS digest ORDER BY o.key",
            {"k": f"{name}={value}"},
        )
    if artifact_type:
        return store.query(
            "MATCH (o:Occurrence)-[:OCCURRENCE_OF]->(art:Artifact) "
            "WHERE art.artifactType = $t OR art.mediaType = $t "
            "RETURN o.key AS key, o.ref AS ref, o.digest AS digest ORDER BY o.key",
            {"t": artifact_type},
        )
    if ref:
        return store.query(
            "MATCH (o:Occurrence {ref: $ref}) "
            "RETURN o.key AS key, o.ref AS ref, o.digest AS digest ORDER BY o.key",
            {"ref": ref},
        )
    return []


def show(store: GraphStore, ref: str) -> dict[str, Any] | None:
    seeds = resolve_seed(store, ref=ref)
    if not seeds:
        return None
    key = seeds[0]
    occ = get_occurrence(store, key)
    if occ is None:
        return None
    annotations = store.query(
        "MATCH (o:Occurrence {key: $k})-[:HAS_ANNOTATION]->(a:Annotation) "
        "RETURN a.name AS name, a.value AS value ORDER BY a.name",
        {"k": key},
    )
    artifact = store.query(
        "MATCH (o:Occurrence {key: $k})-[:OCCURRENCE_OF]->(art:Artifact) "
        "RETURN art.digest AS digest, art.mediaType AS mediaType, art.artifactType AS artifactType",
        {"k": key},
    )
    tags = store.query(
        "MATCH (t:Tag)-[e:POINTED_TO]->(o:Occurrence {key: $k}) "
        "RETURN t.tag AS tag, e.observedAt AS observedAt ORDER BY e.observedAt",
        {"k": key},
    )
    return {
        "occurrence": occ,
        "artifact": artifact[0] if artifact else None,
        "annotations": annotations,
        "tags": tags,
        "referrers": referrers(store, ref=key)["edges"],
        "deleted": bool(occ.get("deletedAt")),
        "path": traverse(store, [key], PATH_RELS, direction="both", max_depth=2),
    }


# -- export -------------------------------------------------------------------


def _node_label(node: dict[str, Any]) -> str:
    """A label that disambiguates occurrences of the same repository by digest."""
    ref = node.get("ref") or node["key"]
    digest = node.get("digest") or ""
    short = digest[7:19] if digest.startswith("sha256:") else digest[:12]
    label = f"{ref}@{short}" if short else str(ref)
    if node.get("deletedAt"):
        label += " (deleted)"
    return label


def to_cytoscape(subgraph: dict[str, Any]) -> dict[str, Any]:
    elements = [{"data": {"id": n["key"], "label": _node_label(n), **n}} for n in subgraph["nodes"]]
    for i, e in enumerate(subgraph["edges"]):
        label = e.get("artifactType") or e["type"]
        elements.append({"data": {"id": f"e{i}", "source": e["from"], "target": e["to"], "label": label, **e}})
    return {"elements": elements}


def _mermaid_label(text: str) -> str:
    # Mermaid labels are quoted; neutralize quotes/newlines to avoid broken output.
    return str(text).replace('"', "#quot;").replace("\n", " ").replace("\r", " ")


def to_mermaid(subgraph: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    ids = {n["key"]: f"n{i}" for i, n in enumerate(subgraph["nodes"])}
    for n in subgraph["nodes"]:
        label = _mermaid_label(_node_label(n))
        lines.append(f'    {ids[n["key"]]}["{label}"]')
    for e in subgraph["edges"]:
        frm, to = ids.get(e["from"]), ids.get(e["to"])
        if frm and to:
            rel = _mermaid_label(e.get("artifactType") or e["type"])
            lines.append(f'    {frm} -->|{rel}| {to}')
    return "\n".join(lines)
