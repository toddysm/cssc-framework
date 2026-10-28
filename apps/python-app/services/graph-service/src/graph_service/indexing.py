"""Build and own the LadybugDB graph the service serves.

A single :class:`GraphIndex` owns the read-write connection (LadybugDB allows one
writer). ``rebuild`` re-reads the committed data files into an ephemeral database;
readiness is gated on a rebuild having succeeded at least once.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from cssc_graph.graph import GraphStore
from cssc_graph.indexer import index_data
from cssc_graph.records import iter_records
from cssc_graph.references import reference_diagnostics
from cssc_graph.validate import default_schema_dir, validate_data

from .config import GraphSettings

logger = logging.getLogger(__name__)


class IndexingError(RuntimeError):
    """Raised when the data root fails validation and cannot be indexed."""

    def __init__(self, diagnostics: list[str]) -> None:
        self.diagnostics = diagnostics
        super().__init__(f"{len(diagnostics)} validation error(s); nothing indexed.")


class GraphNotReady(RuntimeError):
    """Raised when a read is attempted before the graph has been indexed."""


@dataclass
class IndexInfo:
    """Current indexed counts and visible non-fatal reference diagnostics."""
    records: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    root: str = ""
    diagnostics: list[str] = field(default_factory=list)


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

    @contextmanager
    def reading(self) -> Iterator[GraphStore]:
        """Hold the single-writer lock for the duration of a read.

        A concurrent :meth:`rebuild` (which closes and replaces the store) cannot
        run while a query is in flight, and vice versa.
        """

        with self._lock:
            if not self.ready or self._store is None:
                raise GraphNotReady("graph index not ready")
            yield self._store

    def rebuild(self) -> IndexInfo:
        """Validate before replacing derived state; strict failures leave it not ready."""

        settings = self._settings
        with self._lock:
            self.ready = False
            root = settings.data_root
            schema_dir = settings.schema_dir or default_schema_dir(root)
            if root.exists():
                diagnostics = validate_data(root, schema_dir)
                if not diagnostics and settings.strict_references:
                    diagnostics = reference_diagnostics(iter_records(root, schema_dir), strict=True)
                if diagnostics:
                    raise IndexingError([d.format(root) for d in diagnostics])
            if self._store is not None:
                self._store.close()
                self._store = None
            # A fresh, deterministic graph on every rebuild.
            GraphStore.destroy(settings.database_path)
            store = GraphStore(settings.database_path).connect()
            store.init_schema()

            info = IndexInfo(root=str(settings.data_root))
            if root.exists():
                stats = index_data(store, root, schema_dir)
                warnings = [d.format(root) for d in stats.diagnostics]
                for warning in warnings:
                    logger.warning("%s", warning)
                info = IndexInfo(
                    records=stats.records, by_kind=dict(stats.by_kind), root=str(root),
                    diagnostics=warnings,
                )
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
        """Expose counts and reference warnings through readiness and rebuild responses."""
        return {
            "records": self.info.records, "byKind": self.info.by_kind, "root": self.info.root,
            "diagnostics": self.info.diagnostics,
        }
