"""Parsing helpers for promotion tracking issues.

The promote-from-quarantine workflow embeds a machine-readable metadata block in
each tracking issue body, delimited by HTML comment markers and containing a
fenced JSON object. The authoritative ``blocking_cves`` list lives there.
"""

from __future__ import annotations

import json

META_START = "<!-- cssc-metadata:start -->"
META_END = "<!-- cssc-metadata:end -->"
TITLE_PREFIX = "Promotion blocked: "


def parse_metadata(body: str | None) -> dict:
    """Return the JSON object embedded in the issue body, or ``{}``."""

    if not body:
        return {}
    text = body.replace("\r", "")
    start = text.find(META_START)
    end = text.find(META_END)
    if start == -1 or end == -1 or end < start:
        return {}
    block = text[start + len(META_START) : end]
    lines = [
        line
        for line in block.splitlines()
        if line.strip() not in ("```json", "```")
    ]
    raw = "\n".join(lines).strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_blocking_cves(body: str | None) -> list[str]:
    """Extract the ``blocking_cves`` list from the metadata block."""

    cves = parse_metadata(body).get("blocking_cves") or []
    return [str(cve) for cve in cves if str(cve).strip()]


def parse_title(title: str | None) -> tuple[str | None, str | None]:
    """Split a ``Promotion blocked: <image>:<tag>`` title into (image, tag)."""

    if not title or not title.startswith(TITLE_PREFIX):
        return (None, None)
    rest = title[len(TITLE_PREFIX) :].strip()
    if ":" not in rest:
        return (rest or None, None)
    image, tag = rest.rsplit(":", 1)
    return (image or None, tag or None)
