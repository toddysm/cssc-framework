"""Environment-driven configuration for graph-service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _flag(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class GraphSettings:
    """Settings for building and serving the supply-chain graph."""

    data_root: Path
    database_path: Path
    schema_dir: Path | None
    rebuild_on_startup: bool
    max_depth: int


def graph_settings() -> GraphSettings:
    """Build :class:`GraphSettings` from the process environment.

    Recognised variables:

    * ``DATA_ROOT`` — directory of committed supply-chain-graph records to index
      (defaults to ``supply-chain-graph``; a git-synced copy in the pod).
    * ``DATABASE_PATH`` — LadybugDB directory the service owns (must be writable).
    * ``SCHEMA_DIR`` — schema directory (defaults to ``<DATA_ROOT>/schema``).
    * ``REBUILD_ON_STARTUP`` — rebuild the database from files on start (default
      ``true``; the single writer owns an ephemeral graph).
    * ``MAX_DEPTH`` — hard cap applied to every traversal depth (default ``6``).
    """

    schema_env = os.environ.get("SCHEMA_DIR")
    return GraphSettings(
        data_root=Path(os.environ.get("DATA_ROOT", "supply-chain-graph")),
        database_path=Path(os.environ.get("DATABASE_PATH", ".graph")),
        schema_dir=Path(schema_env) if schema_env else None,
        rebuild_on_startup=_flag(os.environ.get("REBUILD_ON_STARTUP", "true")),
        max_depth=int(os.environ.get("MAX_DEPTH", "6")),
    )
