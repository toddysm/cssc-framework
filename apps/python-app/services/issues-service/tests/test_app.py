import httpx
from fastapi.testclient import TestClient

from cssc_common.github import GitHubClient
from issues_service.app import create_app
from issues_service.client import IssuesClient


def _body(repo: str, tag: str, cves: list[str]) -> str:
    cve_json = ", ".join(f'"{c}"' for c in cves)
    return (
        f"Image `{repo}:{tag}` failed the gate.\n\n"
        "<!-- cssc-metadata:start -->\n"
        "```json\n"
        f'{{"source_repo": "{repo}", "tag": "{tag}", "blocking_cves": [{cve_json}]}}\n'
        "```\n"
        "<!-- cssc-metadata:end -->\n"
    )


SEARCH = {
    "items": [
        {
            "number": 77,
            "title": "Promotion blocked: ghcr.io/toddysm/quarantine/python:3.14-slim",
            "html_url": "https://github.com/toddysm/cssc-framework/issues/77",
            "state": "open",
            "labels": [{"name": "promotion-pending"}],
            "body": _body(
                "ghcr.io/toddysm/quarantine/python",
                "3.14-slim",
                ["CVE-2024-1234", "CVE-2024-5678"],
            ),
        },
        {
            "number": 70,
            "title": "Promotion blocked: ghcr.io/toddysm/quarantine/node:20-slim",
            "html_url": "https://github.com/toddysm/cssc-framework/issues/70",
            "state": "closed",
            "labels": [{"name": "promotion-approved"}],
            "body": _body("ghcr.io/toddysm/quarantine/node", "20-slim", ["CVE-2023-9999"]),
        },
        {
            "number": 5,
            "title": "Some unrelated issue",
            "html_url": "https://github.com/toddysm/cssc-framework/issues/5",
            "state": "open",
            "labels": [{"name": "bug"}],
            "body": "",
        },
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    if "/search/issues" in request.url.path:
        return httpx.Response(200, json=SEARCH)
    return httpx.Response(404, json={"message": "not found"})


def _app():
    transport = httpx.MockTransport(_handler)
    http = httpx.Client(base_url="https://api.github.com", transport=transport)
    github = GitHubClient(client=http, owner="toddysm", repo="cssc-framework", cache_ttl=0)
    return create_app(IssuesClient(github))


def test_lists_only_promotion_issues():
    client = TestClient(_app())
    body = client.get("/issues").json()
    numbers = sorted(i["number"] for i in body)
    assert numbers == [70, 77]


def test_open_issue_pending_with_cves():
    client = TestClient(_app())
    body = client.get("/issues").json()
    issue = next(i for i in body if i["number"] == 77)
    assert issue["state"] == "open"
    assert issue["outcome"] == "pending"
    assert issue["image"] == "ghcr.io/toddysm/quarantine/python"
    assert issue["tag"] == "3.14-slim"
    assert issue["blocking_cves"] == ["CVE-2024-1234", "CVE-2024-5678"]


def test_closed_issue_approved():
    client = TestClient(_app())
    body = client.get("/issues").json()
    issue = next(i for i in body if i["number"] == 70)
    assert issue["state"] == "closed"
    assert issue["outcome"] == "approved"


def test_filter_by_image():
    client = TestClient(_app())
    body = client.get(
        "/issues", params={"image": "ghcr.io/toddysm/quarantine/python"}
    ).json()
    assert [i["number"] for i in body] == [77]


def test_filter_by_state():
    client = TestClient(_app())
    body = client.get("/issues", params={"state": "closed"}).json()
    assert [i["number"] for i in body] == [70]


def test_healthz():
    client = TestClient(_app())
    assert client.get("/healthz").json() == {"status": "ok"}
