"""Observability stage: the supply-chain graph.

Surfaces the ``graph-service`` index summary and lets the operator explore a
bounded neighborhood of any occurrence (rendered by the ``/graph/neighborhood``
route). Adding this provider is all it takes for the UI to show the stage.
"""

from __future__ import annotations

from typing import Any

from ..clients import GraphClient
from .base import Stage


class GraphProvider:
    stage = Stage(
        id="observability",
        title="Supply chain graph",
        description="Artifact lineage recorded by the pipeline: mirror, promote, build, and deploy edges.",
        order=5,
    )

    def __init__(self, graph: GraphClient) -> None:
        self._graph = graph

    def get_data(self) -> dict[str, Any]:
        return self._graph.readiness()
