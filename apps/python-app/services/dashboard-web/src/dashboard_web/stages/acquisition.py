"""The Acquisition stage provider.

It correlates mirrored images (from packages-service) with their promotion
tracking issues (from issues-service) and builds CVE links for the UI.
"""

from __future__ import annotations

from typing import Any

from ..clients import IssuesServiceClient, PackagesServiceClient
from .base import Stage


class AcquisitionProvider:
    stage = Stage(
        id="acquisition",
        title="Acquisition",
        description=(
            "Images mirrored from external registries, and the issues blocking "
            "their promotion from quarantine."
        ),
        order=1,
    )

    def __init__(
        self,
        packages: PackagesServiceClient,
        issues: IssuesServiceClient,
        namespace: str = "quarantine",
        cve_base_url: str = "https://nvd.nist.gov/vuln/detail/",
    ) -> None:
        self._packages = packages
        self._issues = issues
        self._namespace = namespace
        self._cve_base_url = cve_base_url

    def _cve_url(self, cve_id: str) -> str:
        return f"{self._cve_base_url}{cve_id}"

    def _issues_for(
        self, image_name: str, all_issues: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for issue in all_issues:
            image = issue.get("image") or ""
            if image == image_name or image.endswith(f"/{image_name}"):
                enriched = dict(issue)
                enriched["cves"] = [
                    {"id": cve, "url": self._cve_url(cve)}
                    for cve in issue.get("blocking_cves", [])
                ]
                matched.append(enriched)
        # Open issues first, then by issue number.
        matched.sort(key=lambda i: (i.get("state") != "open", i.get("number", 0)))
        return matched

    def get_data(self) -> dict[str, Any]:
        packages = self._packages.get_packages(self._namespace)
        all_issues = self._issues.get_issues(state="all")
        images = [
            {
                "name": pkg.get("name", ""),
                "visibility": pkg.get("visibility"),
                "updated_at": pkg.get("updated_at"),
                "tag_count": pkg.get("tag_count"),
                "issues": self._issues_for(pkg.get("name", ""), all_issues),
            }
            for pkg in packages
        ]
        return {"namespace": self._namespace, "images": images}
