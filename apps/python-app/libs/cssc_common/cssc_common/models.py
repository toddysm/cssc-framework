"""Pydantic models shared across the CSSC Dashboard services."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
