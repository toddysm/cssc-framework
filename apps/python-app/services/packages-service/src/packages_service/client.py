"""GHCR package inventory backed by the GitHub Packages API."""

from __future__ import annotations

from urllib.parse import quote

from cssc_common import (
    MIRROR_HISTORY_TAG,
    GitHubClient,
    MirroredImage,
    MirrorHistoryEntry,
    OciRegistryClient,
    Tag,
)


class PackagesClient:
    """Read container packages and their tags for the configured owner."""

    def __init__(
        self,
        github: GitHubClient,
        registry: OciRegistryClient | None = None,
    ) -> None:
        self._gh = github
        self._registry = registry

    def _owner_root(self) -> str:
        """Return the Packages API root for the owner (user vs org).

        The GitHub Packages API uses ``/users/{owner}`` for user accounts and
        ``/orgs/{owner}`` for organizations; the owner type comes from config.
        """

        prefix = "orgs" if self._gh.owner_type == "org" else "users"
        return f"/{prefix}/{self._gh.owner}"

    def list_packages(self, namespace: str = "quarantine") -> list[MirroredImage]:
        """List container packages whose name starts with ``<namespace>/``.

        These are the "mirrored" images — the ones the ``mirror-*`` workflows
        copy into the ``quarantine/*`` namespace.
        """

        raw = self._gh.get_all(
            f"{self._owner_root()}/packages",
            params={"package_type": "container", "per_page": 100},
        )
        prefix = f"{namespace}/" if namespace else ""
        images: list[MirroredImage] = []
        for pkg in raw:
            name = pkg.get("name", "")
            if prefix and not name.startswith(prefix):
                continue
            images.append(
                MirroredImage(
                    name=name,
                    namespace=namespace,
                    visibility=pkg.get("visibility"),
                    updated_at=pkg.get("updated_at"),
                    tag_count=pkg.get("version_count"),
                )
            )
        return images

    def list_tags(self, name: str) -> list[Tag]:
        """List the tags of a single container package.

        ``name`` may contain slashes (for example ``quarantine/python``); it is
        URL-encoded before being placed in the API path.
        """

        encoded = quote(name, safe="")
        versions = self._gh.get_all(
            f"{self._owner_root()}/packages/container/{encoded}/versions",
            params={"per_page": 100},
        )
        tags: list[Tag] = []
        for version in versions:
            container = (version.get("metadata") or {}).get("container") or {}
            for tag in container.get("tags") or []:
                tags.append(
                    Tag(
                        tag=tag,
                        digest=version.get("name"),
                        updated_at=version.get("updated_at"),
                    )
                )
        return tags

    def get_history(self, name: str) -> list[MirrorHistoryEntry]:
        """Return the recorded synchronization history for a repository.

        Reads the ``<name>:mirror-history`` OCI artifact from the registry.
        Returns an empty list when no registry client is configured or the
        repository has no history yet (the reserved tag is absent).
        """

        if self._registry is None:
            return []
        document = self._registry.fetch_json_artifact(name, MIRROR_HISTORY_TAG)
        if not document:
            return []
        entries = document.get("entries") or []
        return [MirrorHistoryEntry.model_validate(entry) for entry in entries]
