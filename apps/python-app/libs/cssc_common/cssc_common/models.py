"""Pydantic models shared across the CSSC Dashboard services."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Tag(BaseModel):
    """A single tag of a container package."""

    tag: str
    digest: str | None = None
    updated_at: str | None = None


class MirroredImage(BaseModel):
    """A mirrored container package (an image under a namespace)."""

    name: str
    namespace: str
    visibility: str | None = None
    updated_at: str | None = None
    tag_count: int | None = None


class PromotionIssue(BaseModel):
    """A promotion tracking issue for a blocked image:tag."""

    number: int
    title: str
    url: str
    state: str
    outcome: str
    image: str | None = None
    tag: str | None = None
    blocking_cves: list[str] = Field(default_factory=list)


class Cve(BaseModel):
    """A CVE identifier paired with its database URL (rendered by the UI)."""

    id: str
    url: str


class MirrorHistoryEntry(BaseModel):
    """One recorded synchronization from the mirror-history artifact.

    Accepts the camelCase keys used in the on-registry JSON and exposes
    snake_case attributes to the services.
    """

    model_config = ConfigDict(populate_by_name=True)

    source_tag: str | None = Field(default=None, alias="sourceTag")
    source_digest: str | None = Field(default=None, alias="sourceDigest")
    dest_tag: str | None = Field(default=None, alias="destTag")
    synced_at: str | None = Field(default=None, alias="syncedAt")
    run_url: str | None = Field(default=None, alias="runUrl")
    run_id: str | None = Field(default=None, alias="runId")
    run_attempt: str | None = Field(default=None, alias="runAttempt")
    force: bool = False
