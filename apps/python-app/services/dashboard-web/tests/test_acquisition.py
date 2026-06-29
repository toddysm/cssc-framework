from dashboard_web.stages.acquisition import AcquisitionProvider


class FakePackages:
    def __init__(self, data):
        self._data = data

    def get_packages(self, namespace):
        return self._data


class FakeIssues:
    def __init__(self, data):
        self._data = data

    def get_issues(self, image=None, tag=None, state="all"):
        return self._data


PACKAGES = [
    {
        "name": "quarantine/python",
        "visibility": "private",
        "updated_at": "2026-06-01T00:00:00Z",
        "tag_count": 2,
    }
]

ISSUES = [
    {
        "number": 77,
        "title": "Promotion blocked: ghcr.io/toddysm/quarantine/python:3.14-slim",
        "url": "https://github.com/toddysm/cssc-framework/issues/77",
        "state": "open",
        "outcome": "pending",
        "image": "ghcr.io/toddysm/quarantine/python",
        "tag": "3.14-slim",
        "blocking_cves": ["CVE-2024-1234", "CVE-2024-5678"],
    },
    {
        "number": 40,
        "title": "Promotion blocked: ghcr.io/toddysm/quarantine/node:20",
        "url": "https://github.com/toddysm/cssc-framework/issues/40",
        "state": "closed",
        "outcome": "approved",
        "image": "ghcr.io/toddysm/quarantine/node",
        "tag": "20",
        "blocking_cves": [],
    },
]


def test_stage_metadata():
    provider = AcquisitionProvider(FakePackages([]), FakeIssues([]))
    assert provider.stage.id == "acquisition"
    assert provider.stage.order == 1


def test_get_data_correlates_issues_and_builds_cve_urls():
    provider = AcquisitionProvider(
        FakePackages(PACKAGES),
        FakeIssues(ISSUES),
        namespace="quarantine",
        cve_base_url="https://nvd.nist.gov/vuln/detail/",
    )
    data = provider.get_data()

    assert data["namespace"] == "quarantine"
    assert len(data["images"]) == 1

    image = data["images"][0]
    assert image["name"] == "quarantine/python"
    # Only the python issue correlates (node issue does not match this image).
    assert [i["number"] for i in image["issues"]] == [77]

    cves = image["issues"][0]["cves"]
    assert cves == [
        {"id": "CVE-2024-1234", "url": "https://nvd.nist.gov/vuln/detail/CVE-2024-1234"},
        {"id": "CVE-2024-5678", "url": "https://nvd.nist.gov/vuln/detail/CVE-2024-5678"},
    ]


def test_get_data_handles_image_without_issues():
    provider = AcquisitionProvider(FakePackages(PACKAGES), FakeIssues([]))
    image = provider.get_data()["images"][0]
    assert image["issues"] == []
