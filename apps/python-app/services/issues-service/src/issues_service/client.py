"""Promotion tracking issues backed by the GitHub Search API."""

from __future__ import annotations

from cssc_common import GitHubClient, PromotionIssue

from .metadata import parse_blocking_cves, parse_title

PROMOTION_LABELS = {
    "promotion-pending",
    "promotion-approved",
    "promotion-denied",
}


class IssuesClient:
    """Read promotion tracking issues for the configured repository."""

    def __init__(self, github: GitHubClient) -> None:
        self._gh = github

    def list_issues(
        self,
        image: str | None = None,
        tag: str | None = None,
        state: str = "all",
    ) -> list[PromotionIssue]:
        """List promotion tracking issues, optionally filtered.

        Issues are matched by the ``Promotion blocked:`` title prefix and a
        promotion label; ``outcome`` is derived from the label
        (``approved`` / ``denied`` / ``pending``) and ``blocking_cves`` from the
        embedded metadata block.
        """

        query = (
            f"repo:{self._gh.owner}/{self._gh.repo} is:issue "
            'in:title "Promotion blocked:"'
        )
        items = self._gh.get_all(
            "/search/issues",
            params={"q": query, "per_page": 100},
            items_key="items",
        )

        issues: list[PromotionIssue] = []
        for item in items:
            labels = {label.get("name") for label in item.get("labels", [])}
            if not (labels & PROMOTION_LABELS):
                continue

            issue_state = item.get("state", "")
            if state and state != "all" and issue_state != state:
                continue

            img, tg = parse_title(item.get("title"))
            if image and img != image:
                continue
            if tag and tg != tag:
                continue

            if "promotion-approved" in labels:
                outcome = "approved"
            elif "promotion-denied" in labels:
                outcome = "denied"
            else:
                outcome = "pending"

            issues.append(
                PromotionIssue(
                    number=item.get("number"),
                    title=item.get("title", ""),
                    url=item.get("html_url", ""),
                    state=issue_state,
                    outcome=outcome,
                    image=img,
                    tag=tg,
                    blocking_cves=parse_blocking_cves(item.get("body")),
                )
            )
        return issues
