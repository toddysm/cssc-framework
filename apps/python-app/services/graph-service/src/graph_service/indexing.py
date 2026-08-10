"""Build and own the LadybugDB graph the service serves.

A single :class:`GraphIndex` owns the read-write connection (LadybugDB allows one
writer). ``rebuild`` re-reads the committed data files into an ephemeral database;
readiness is gated on a rebuild having succeeded at least once.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cssc_graph.graph import GraphStore
from cssc_graph.indexer import index_data
from cssc_graph.validate import default_schema_dir, validate_data

from .config import GraphSettings

logger = logging.getLogger(__name__)


class IndexingError(RuntimeError):
    """Raised when the data root fails validation and cannot be indexed."""

    def __init__(self, diagnostics: list[str]) -> None:
        self.diagnostics = diagnostics
        super().__init__(f"{len(diagnostics)} validation error(s); nothing indexed.")


@dataclass
class IndexInfo:
    records: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    root: str = ""


class GraphIndex:
    """Owns the graph store and rebuilds it from the data root on demand."""

    def __init__(self, settings: GraphSettings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._store: GraphStore | None = None
        self.ready = False
        self.info = IndexInfo()

    @property
    def store(self) -> GraphStore | None:
        return self._store

    def rebuild(self) -> IndexInfo:
        """(Re)build the database from the data root; single writer via a lock."""

        settings = self._settings
        with self._lock:
            self.ready = False
            if self._store is not None:
                self._store.close()
                self._store = None
            # A fresh, deterministic graph on every rebuild.
            GraphStore.destroy(settings.database_path)
            store = GraphStore(settings.database_path).connect()
            store.init_schema()

            info = IndexInfo(root=str(settings.data_root))
            root = settings.data_root
            if root.exists():
                schema_dir = settings.schema_dir or default_schema_dir(root)
                diagnostics = validate_data(root, schema_dir)
                if diagnostics:
                    store.close()
                    raise IndexingError([d.format(root) for d in diagnostics])
                stats = index_data(store, root, schema_dir)
                info = IndexInfo(records=stats.records, by_kind=dict(stats.by_kind), root=str(root))
            else:
                logger.warning("data root %s does not exist; serving an empty graph", root)

            self._store = store
            self.info = info
            self.ready = True
            logger.info("indexed %d record(s) from %s", info.records, info.root)
            return info

    def close(self) -> None:
        with self._lock:
            if self._store is not None:
                self._store.close()
                self._store = None
            self.ready = False

    def as_dict(self) -> dict[str, Any]:
        return {"records": self.info.records, "byKind": self.info.by_kind, "root": self.info.root}
