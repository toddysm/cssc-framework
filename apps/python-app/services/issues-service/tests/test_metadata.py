from issues_service.metadata import (
    parse_blocking_cves,
    parse_metadata,
    parse_title,
)

BODY = """Image `ghcr.io/toddysm/quarantine/python:3.14-slim` failed the gate.

<!-- cssc-metadata:start -->
```json
{"source_repo": "ghcr.io/toddysm/quarantine/python", "tag": "3.14-slim", "blocking_cves": ["CVE-2024-1234", "CVE-2024-5678"]}
```
<!-- cssc-metadata:end -->
"""


def test_parse_metadata_extracts_json():
    data = parse_metadata(BODY)
    assert data["tag"] == "3.14-slim"
    assert data["blocking_cves"] == ["CVE-2024-1234", "CVE-2024-5678"]


def test_parse_metadata_handles_crlf():
    data = parse_metadata(BODY.replace("\n", "\r\n"))
    assert data["blocking_cves"] == ["CVE-2024-1234", "CVE-2024-5678"]


def test_parse_metadata_missing_block():
    assert parse_metadata("no metadata here") == {}
    assert parse_metadata(None) == {}


def test_parse_metadata_malformed_json():
    bad = "<!-- cssc-metadata:start -->\n```json\n{not json}\n```\n<!-- cssc-metadata:end -->"
    assert parse_metadata(bad) == {}


def test_parse_blocking_cves():
    assert parse_blocking_cves(BODY) == ["CVE-2024-1234", "CVE-2024-5678"]
    assert parse_blocking_cves("nothing") == []


def test_parse_title():
    assert parse_title("Promotion blocked: ghcr.io/toddysm/quarantine/python:3.14-slim") == (
        "ghcr.io/toddysm/quarantine/python",
        "3.14-slim",
    )
    assert parse_title("Unrelated issue") == (None, None)
    assert parse_title(None) == (None, None)
