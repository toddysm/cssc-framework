"""Shared RFC 3339 validation and exact ordering for recorded graph evidence."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from fractions import Fraction


def _parts(value: str) -> tuple[datetime, bool, str]:
    """Parse RFC 3339, retaining leap-second and exact fractional evidence."""
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2})(?:\.(\d+))?([Zz]|[+-]\d{2}:\d{2})",
        value,
    )
    if match is None:
        raise ValueError(
            f"observation timestamp requires an RFC 3339 timezone: {value!r}"
        )
    whole, fraction, zone = match.groups()
    leap_second = whole.endswith(":60")
    # Position leap seconds after every fraction of :59, not at the next :00.
    parseable = whole[:-2] + "59" if leap_second else whole
    timestamp = datetime.fromisoformat(parseable.upper() + zone.upper()).astimezone(UTC)
    return timestamp, leap_second, fraction or ""


def instant(value: str) -> tuple[datetime, bool, Fraction]:
    """Order real instants exactly, including schema-valid sub-microsecond fractions."""
    timestamp, leap_second, fraction = _parts(value)
    return timestamp, leap_second, Fraction(int(fraction or "0"), 10 ** len(fraction))


def utc(value: str) -> str:
    """Normalize a timestamp to UTC while retaining its exact fractional instant."""
    timestamp, leap_second, fraction = _parts(value)
    digits = fraction.rstrip("0")
    suffix = f".{digits}" if digits else ""
    whole = timestamp.isoformat(timespec="seconds").removesuffix("+00:00")
    if leap_second:
        whole = whole[:-2] + "60"
    return whole + suffix + "Z"
