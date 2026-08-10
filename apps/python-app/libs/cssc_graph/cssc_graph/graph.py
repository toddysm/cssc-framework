"""LadybugDB-backed graph store: schema DDL and a small query helper.

One process owns one read-write database. The schema is created with
``IF NOT EXISTS`` and all writes use ``MERGE`` so indexing is idempotent — a full
rebuild and an incremental pass converge to the same graph.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Sequence

# Node and relationship tables. Occurrence is the fully-qualified node
# (registry + repository + digest); Artifact is the immutable digest.
SCHEMA_DDL: tuple[str, ...] = (
    "CREATE NODE TABLE IF NOT EXISTS Artifact("
    "digest STRING, mediaType STRING, artifactType STRING, PRIMARY KEY(digest))",
    "CREATE NODE TABLE IF NOT EXISTS Occurrence("
    "key STRING, registry STRING, repository STRING, digest STRING, ref STRING, "
    "PRIMARY KEY(key))",
    "CREATE NODE TABLE IF NOT EXISTS Tag("
    "key STRING, registry STRING, repository STRING, tag STRING, ref STRING, "
    "PRIMARY KEY(key))",
    "CREATE NODE TABLE IF NOT EXISTS Deployment("
    "key STRING, cluster STRING, namespace STRING, PRIMARY KEY(key))",
    "CREATE REL TABLE IF NOT EXISTS OCCURRENCE_OF(FROM Occurrence TO Artifact)",
    "CREATE REL TABLE IF NOT EXISTS MIRRORED_FROM("
    "FROM Occurrence TO Occurrence, tag STRING, runUrl STRING, recordedAt STRING)",
    "CREATE REL TABLE IF NOT EXISTS PROMOTED_FROM("
    "FROM Occurrence TO Occurrence, tag STRING, runUrl STRING, issueUrl STRING, "
    "recordedAt STRING)",
    "CREATE REL TABLE IF NOT EXISTS BUILT_FROM("
    "FROM Occurrence TO Occurrence, tag STRING, buildVersion STRING, "
    "runUrl STRING, recordedAt STRING)",
    "CREATE REL TABLE IF NOT EXISTS POINTED_TO("
    "FROM Tag TO Occurrence, observedAt STRING, digest STRING, runUrl STRING)",
    "CREATE REL TABLE IF NOT EXISTS RUNS("
    "FROM Deployment TO Occurrence, chart STRING, chartVersion STRING, "
    "runUrl STRING, recordedAt STRING)",
)


class GraphStore:
    """A thin wrapper over a LadybugDB database and connection."""

    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._db: Any = None
        self._conn: Any = None

    # -- lifecycle ----------------------------------------------------------

    def connect(self) -> "GraphStore":
        import ladybug as lb  # lazy: only the graph commands need the native dep

        self._db = lb.Database(str(self._path))
        self._conn = lb.Connection(self._db)
        return self

    def init_schema(self) -> None:
        for ddl in SCHEMA_DDL:
            self.execute(ddl)

    def close(self) -> None:
        self._conn = None
        self._db = None

    def __enter__(self) -> "GraphStore":
        return self.connect()

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def destroy(database_path: str | Path) -> None:
        """Delete an existing database directory/file for a clean rebuild."""

        path = Path(database_path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    # -- queries ------------------------------------------------------------

    def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        if self._conn is None:  # pragma: no cover - guarded by connect()
            raise RuntimeError("GraphStore is not connected")
        return self._conn.execute(query, params) if params else self._conn.execute(query)

    def query(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run a query and return rows as dicts keyed by the returned columns."""

        result = self.execute(query, params)
        columns: Sequence[str] = result.get_column_names()
        rows: list[dict[str, Any]] = []
        while result.has_next():
            rows.append(dict(zip(columns, result.get_next())))
        return rows

    def scalar(self, query: str, params: dict[str, Any] | None = None) -> Any:
        rows = self.query(query, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))
