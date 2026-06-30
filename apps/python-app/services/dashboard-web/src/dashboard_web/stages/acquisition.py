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
        # Normalise once so a CVE_BASE_URL configured without a trailing slash
        # still produces well-formed links.
        self._cve_base_url = (
            cve_base_url if cve_base_url.endswith("/") else f"{cve_base_url}/"
        )

    def _cve_url(self, cve_id: str) -> str:
        return f"{self._cve_base_url}{cve_id}"

    def _enrich(self, issue: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(issue)
        enriched["cves"] = [
            {"id": cve, "url": self._cve_url(cve)}
            for cve in issue.get("blocking_cves", [])
        ]
        return enriched

    @staticmethod
    def _matches(image: str, image_name: str) -> bool:
        return image == image_name or image.endswith(f"/{image_name}")

    @staticmethod
    def _sort_issues(issues: list[dict[str, Any]]) -> None:
        # Open issues first, then by issue number.
        issues.sort(key=lambda i: (i.get("state") != "open", i.get("number", 0)))

    def get_data(self) -> dict[str, Any]:
        packages = self._packages.get_packages(self._namespace)
        all_issues = self._issues.get_issues(state="all")

        images: list[dict[str, Any]] = []
        matched_numbers: set[Any] = set()

        for pkg in packages:
            name = pkg.get("name", "")
            issues: list[dict[str, Any]] = []
            for issue in all_issues:
                if self._matches(issue.get("image") or "", name):
                    issues.append(self._enrich(issue))
                    matched_numbers.add(issue.get("number"))
            self._sort_issues(issues)
            images.append(
                {
                    "name": name,
                    "visibility": pkg.get("visibility"),
                    "updated_at": pkg.get("updated_at"),
                    "tag_count": pkg.get("tag_count"),
                    "in_quarantine": True,
                    "issues": issues,
                }
            )

        # Guarantee every promotion-pending issue is listed, even when its image
        # is no longer a current quarantine package — group these as orphan
        # cards so a blocked image is never silently hidden.
        orphans: dict[str, list[dict[str, Any]]] = {}
        for issue in all_issues:
            if (
                issue.get("outcome") == "pending"
                and issue.get("number") not in matched_numbers
            ):
                key = issue.get("image") or "(unknown image)"
                orphans.setdefault(key, []).append(self._enrich(issue))

        for image_name, issues in sorted(orphans.items()):
            self._sort_issues(issues)
            images.append(
                {
                    "name": image_name,
                    "visibility": None,
                    "updated_at": None,
                    "tag_count": None,
                    "in_quarantine": False,
                    "issues": issues,
                }
            )

        return {"namespace": self._namespace, "images": images}
