"""FastAPI application for packages-service."""

from __future__ import annotations

from fastapi import FastAPI, Query

from cssc_common import GitHubClient, github_settings

from .client import PackagesClient


def build_client() -> PackagesClient:
    settings = github_settings()
    github = GitHubClient(
        token=settings.token,
        owner=settings.owner,
        owner_type=settings.owner_type,
        repo=settings.repo,
        api_url=settings.api_url,
        cache_ttl=settings.cache_ttl,
    )
    return PackagesClient(github)


def create_app(client: PackagesClient | None = None) -> FastAPI:
    """Build the FastAPI app.

    A ``client`` may be injected for tests; otherwise it is lazily constructed
    from the environment on first use.
    """

    app = FastAPI(title="packages-service", version="0.1.0")
    app.state.client = client

    def get_client() -> PackagesClient:
        if app.state.client is None:
            app.state.client = build_client()
        return app.state.client

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/packages")
    def list_packages(namespace: str = Query("quarantine")) -> list[dict]:
        return [image.model_dump() for image in get_client().list_packages(namespace)]

    @app.get("/packages/{name:path}/tags")
    def list_tags(name: str) -> list[dict]:
        return [tag.model_dump() for tag in get_client().list_tags(name)]

    return app


app = create_app()
