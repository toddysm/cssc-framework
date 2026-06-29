"""The stage registry and provider interface.

Stages are the extensibility seam of the dashboard: each CSSC framework stage is
described by a :class:`Stage` and produced by a :class:`StageProvider`. Adding a
stage means registering a new provider — the UI renders any registered stage
generically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class Stage:
    id: str
    title: str
    description: str
    order: int


@runtime_checkable
class StageProvider(Protocol):
    """Produces the data for a single stage."""

    @property
    def stage(self) -> Stage: ...

    def get_data(self) -> dict[str, Any]: ...


class StageRegistry:
    """An ordered collection of stage providers keyed by stage id."""

    def __init__(self) -> None:
        self._providers: dict[str, StageProvider] = {}

    def register(self, provider: StageProvider) -> StageProvider:
        self._providers[provider.stage.id] = provider
        return provider

    def stages(self) -> list[Stage]:
        return [
            provider.stage
            for provider in sorted(
                self._providers.values(), key=lambda p: p.stage.order
            )
        ]

    def provider(self, stage_id: str) -> StageProvider | None:
        return self._providers.get(stage_id)
