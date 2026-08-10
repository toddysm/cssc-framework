"""Fold validated records into the graph via idempotent MERGE statements."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .graph import GraphStore
from .identity import (
    make_occurrence_key,
    make_ref,
    split_ref,
    tag_key,
)
from .records import iter_records


@dataclass
class IndexStats:
    """Counts produced by an indexing run."""

    records: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)

    def bump(self, kind: str) -> None:
        self.records += 1
        self.by_kind[kind] = self.by_kind.get(kind, 0) + 1


class Indexer:
    """Writes records into a :class:`GraphStore`."""

    def __init__(self, store: GraphStore) -> None:
        self._store = store

    # -- node helpers -------------------------------------------------------

    def _merge_occurrence(self, registry: str, repository: str, digest: str) -> str:
        key = make_occurrence_key(registry, repository, digest)
        self._store.execute(
            "MERGE (o:Occurrence {key: $key}) "
            "SET o.registry = $registry, o.repository = $repository, "
            "o.digest = $digest, o.ref = $ref",
            {
                "key": key,
                "registry": registry,
                "repository": repository,
                "digest": digest,
                "ref": make_ref(registry, repository),
            },
        )
        self._store.execute("MERGE (a:Artifact {digest: $digest})", {"digest": digest})
        self._store.execute(
            "MATCH (o:Occurrence {key: $key}), (a:Artifact {digest: $digest}) "
            "MERGE (o)-[:OCCURRENCE_OF]->(a)",
            {"key": key, "digest": digest},
        )
        return key

    def _merge_occurrence_from(self, occ: Mapping[str, Any]) -> str:
        return self._merge_occurrence(occ["registry"], occ["repository"], occ["digest"])

    def _set_artifact_metadata(self, digest: str, media_type: str, artifact_type: str) -> None:
        self._store.execute(
            "MERGE (a:Artifact {digest: $digest}) "
            "SET a.mediaType = $mediaType, a.artifactType = $artifactType",
            {"digest": digest, "mediaType": media_type or "", "artifactType": artifact_type or ""},
        )

    def _merge_tag(self, registry: str, repository: str, tag: str) -> str:
        key = tag_key(registry, repository, tag)
        self._store.execute(
            "MERGE (t:Tag {key: $key}) "
            "SET t.registry = $registry, t.repository = $repository, "
            "t.tag = $tag, t.ref = $ref",
            {
                "key": key,
                "registry": registry,
                "repository": repository,
                "tag": tag,
                "ref": make_ref(registry, repository),
            },
        )
        return key

    def _merge_deployment(self, cluster: str, namespace: str) -> str:
        key = f"{cluster}/{namespace}"
        self._store.execute(
            "MERGE (d:Deployment {key: $key}) "
            "SET d.cluster = $cluster, d.namespace = $namespace",
            {"key": key, "cluster": cluster, "namespace": namespace},
        )
        return key

    # -- record dispatch ----------------------------------------------------

    def index_record(self, record: Mapping[str, Any]) -> None:
        kind = record.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError(f"record is missing a string 'kind': {kind!r}")
        handler = getattr(self, f"_index_{_snake(kind)}", None)
        if handler is None:
            raise ValueError(f"no indexer for kind {kind!r}")
        handler(record)

    def index_records(self, records) -> IndexStats:
        stats = IndexStats()
        for record in records:
            self.index_record(record)
            stats.bump(record["kind"])
        return stats

    def _index_artifact_observed(self, record: Mapping[str, Any]) -> None:
        occ = record["occurrence"]
        self._merge_occurrence_from(occ)
        artifact = record.get("artifact", {})
        self._set_artifact_metadata(
            occ["digest"], artifact.get("mediaType", ""), artifact.get("artifactType", "")
        )

    def _index_artifact_mirrored(self, record: Mapping[str, Any]) -> None:
        self._merge_pair_edge(record, "MIRRORED_FROM", key_props=("tag",))

    def _index_artifact_promoted(self, record: Mapping[str, Any]) -> None:
        to_key = self._merge_occurrence_from(record["to"])
        from_key = self._merge_occurrence_from(record["from"])
        evidence = record.get("evidence", {})
        self._store.execute(
            "MATCH (t:Occurrence {key: $to}), (f:Occurrence {key: $from}) "
            "MERGE (t)-[r:PROMOTED_FROM {tag: $tag}]->(f) "
            "SET r.runUrl = $runUrl, r.issueUrl = $issueUrl, r.recordedAt = $recordedAt",
            {
                "to": to_key,
                "from": from_key,
                "tag": record["tag"],
                "runUrl": _run_url(record),
                "issueUrl": evidence.get("issueUrl", "") or record.get("source", {}).get("issueUrl", ""),
                "recordedAt": record.get("recordedAt", ""),
            },
        )

    def _index_artifact_built(self, record: Mapping[str, Any]) -> None:
        image_key = self._merge_occurrence_from(record["image"])
        base = record["base"]
        registry, repository = split_ref(base["name"])
        base_key = self._merge_occurrence(registry, repository, base["digest"])
        self._store.execute(
            "MATCH (i:Occurrence {key: $image}), (b:Occurrence {key: $base}) "
            "MERGE (i)-[r:BUILT_FROM]->(b) "
            "SET r.tag = $tag, r.buildVersion = $buildVersion, "
            "r.runUrl = $runUrl, r.recordedAt = $recordedAt",
            {
                "image": image_key,
                "base": base_key,
                "tag": base.get("tag", ""),
                "buildVersion": record.get("buildVersion", ""),
                "runUrl": _run_url(record),
                "recordedAt": record.get("recordedAt", ""),
            },
        )

    def _index_artifact_deployed(self, record: Mapping[str, Any]) -> None:
        image_key = self._merge_occurrence_from(record["image"])
        env = record.get("environment", {})
        dep_key = self._merge_deployment(env.get("cluster", ""), env.get("namespace", ""))
        chart = record.get("chart", {})
        self._store.execute(
            "MATCH (d:Deployment {key: $dep}), (o:Occurrence {key: $image}) "
            "MERGE (d)-[r:RUNS]->(o) "
            "SET r.chart = $chart, r.chartVersion = $chartVersion, "
            "r.runUrl = $runUrl, r.recordedAt = $recordedAt",
            {
                "dep": dep_key,
                "image": image_key,
                "chart": chart.get("name", ""),
                "chartVersion": chart.get("version", ""),
                "runUrl": _run_url(record),
                "recordedAt": record.get("recordedAt", ""),
            },
        )

    def _index_tag_observed(self, record: Mapping[str, Any]) -> None:
        occ = record["occurrence"]
        registry, repository = occ["registry"], occ["repository"]
        digest = record["digest"]
        occ_key = self._merge_occurrence(registry, repository, digest)
        tk = self._merge_tag(registry, repository, record["tag"])
        self._store.execute(
            "MATCH (t:Tag {key: $tag}), (o:Occurrence {key: $occ}) "
            "MERGE (t)-[r:POINTED_TO {observedAt: $observedAt}]->(o) "
            "SET r.digest = $digest, r.runUrl = $runUrl",
            {
                "tag": tk,
                "occ": occ_key,
                "observedAt": record["observedAt"],
                "digest": digest,
                "runUrl": _run_url(record),
            },
        )

    # -- shared edge builder ------------------------------------------------

    def _merge_pair_edge(self, record: Mapping[str, Any], rel: str, key_props: tuple[str, ...]) -> None:
        to_key = self._merge_occurrence_from(record["to"])
        from_key = self._merge_occurrence_from(record["from"])
        merge_props = ", ".join(f"{p}: ${p}" for p in key_props)
        pattern = f"[r:{rel} {{{merge_props}}}]" if key_props else f"[r:{rel}]"
        params = {"to": to_key, "from": from_key, "runUrl": _run_url(record), "recordedAt": record.get("recordedAt", "")}
        for prop in key_props:
            params[prop] = record.get(prop, "")
        self._store.execute(
            f"MATCH (t:Occurrence {{key: $to}}), (f:Occurrence {{key: $from}}) "
            f"MERGE (t)-{pattern}->(f) "
            f"SET r.runUrl = $runUrl, r.recordedAt = $recordedAt",
            params,
        )


def _run_url(record: Mapping[str, Any]) -> str:
    return record.get("source", {}).get("runUrl", "")


def _snake(kind: str) -> str:
    out = []
    for ch in kind:
        if ch.isupper() and out:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def index_data(store: GraphStore, root: Path, schema_dir: Path | None = None) -> IndexStats:
    """Index every record under *root* into *store*."""

    indexer = Indexer(store)
    return indexer.index_records(data for _, data in iter_records(root, schema_dir))
