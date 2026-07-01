"""FastAPI application for issues-service."""

from __future__ import annotations

from fastapi import FastAPI, Query

from cssc_common import GitHubClient, github_settings

from .client import IssuesClient


def build_client() -> IssuesClient:
    settings = github_settings()
    github = GitHubClient(
        token=settings.token,
        owner=settings.owner,
        repo=settings.repo,
        api_url=settings.api_url,
        cache_ttl=settings.cache_ttl,
    )
    return IssuesClient(github)


def create_app(client: IssuesClient | None = None) -> FastAPI:
    app = FastAPI(title="issues-service", version="0.1.0")
    app.state.client = client

    def get_client() -> IssuesClient:
        if app.state.client is None:
            app.state.client = build_client()
        return app.state.client

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/issues")
    def list_issues(
        image: str | None = Query(None),
        tag: str | None = Query(None),
        state: str = Query("all"),
    ) -> list[dict]:
        issues = get_client().list_issues(image=image, tag=tag, state=state)
        return [issue.model_dump() for issue in issues]

    return app


app = create_app()
