"""Load parsed records from the data root (for indexing)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from . import yamlio
from .validate import (
    SOURCES_FILENAME,
    default_schema_dir,
    discover_record_files,
)


def iter_records(root: Path, schema_dir: Path | None = None) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield ``(path, record)`` for every record file under *root*.

    ``sources.yaml`` is skipped (it is configuration, not a graph record).
    Assumes the files have already been validated.
    """

    root = Path(root)
    schema_dir = Path(schema_dir) if schema_dir is not None else default_schema_dir(root)
    for path in discover_record_files(root, schema_dir):
        if path.name == SOURCES_FILENAME:
            continue
        data = yamlio.load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("kind"):
            yield path, data
