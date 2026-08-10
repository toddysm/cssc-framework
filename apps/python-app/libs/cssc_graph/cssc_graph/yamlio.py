"""YAML loading for records.

Records use RFC 3339 timestamps (``recordedAt``, ``observedAt``). PyYAML would
otherwise parse those into ``datetime`` objects, which then fail the schema's
``type: string`` check and cannot be JSON-serialized for the content id. This
loader keeps timestamp scalars as their original strings.
"""

from __future__ import annotations

from typing import Any

import yaml


class RecordLoader(yaml.SafeLoader):
    """A SafeLoader that leaves timestamp scalars as strings."""


RecordLoader.add_constructor(
    "tag:yaml.org,2002:timestamp",
    lambda loader, node: loader.construct_scalar(node),
)


def load(text: str) -> Any:
    """Parse YAML text with timestamps preserved as strings."""

    return yaml.load(text, Loader=RecordLoader)
