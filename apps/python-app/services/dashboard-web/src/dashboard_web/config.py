"""Environment-driven configuration for dashboard-web."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardSettings:
    packages_service_url: str
    issues_service_url: str
    cve_base_url: str
    quarantine_namespace: str


def dashboard_settings() -> DashboardSettings:
    """Build :class:`DashboardSettings` from the environment.

    * ``PACKAGES_SERVICE_URL`` / ``ISSUES_SERVICE_URL`` — upstream capability
      services (default to the in-cluster `Service` DNS names).
    * ``CVE_BASE_URL`` — base for CVE links; the CVE id is appended.
    * ``QUARANTINE_NAMESPACE`` — the namespace treated as "mirrored".
    """

    return DashboardSettings(
        packages_service_url=os.environ.get(
            "PACKAGES_SERVICE_URL", "http://packages-service"
        ).rstrip("/"),
        issues_service_url=os.environ.get(
            "ISSUES_SERVICE_URL", "http://issues-service"
        ).rstrip("/"),
        cve_base_url=os.environ.get(
            "CVE_BASE_URL", "https://nvd.nist.gov/vuln/detail/"
        ),
        quarantine_namespace=os.environ.get("QUARANTINE_NAMESPACE", "quarantine"),
    )
