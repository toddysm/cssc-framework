"""HTTP routes for dashboard-web.

The full page (`GET /`) renders one section per registered stage; each section
lazily loads its body from `GET /stages/{id}/fragment` via htmx. A stage with a
dedicated template (`templates/stages/<id>.html`) uses it; otherwise a generic
fallback renders the raw data.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound

from ..clients import GraphClient
from ..stages.base import StageRegistry

logger = logging.getLogger(__name__)


def _template_exists(templates: Jinja2Templates, name: str) -> bool:
    try:
        templates.get_template(name)
        return True
    except TemplateNotFound:
        return False


def add_routes(
    app: FastAPI,
    registry: StageRegistry,
    templates: Jinja2Templates,
    graph: GraphClient | None = None,
) -> None:
    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"stages": registry.stages()},
        )

    @app.get("/stages/{stage_id}/fragment", response_class=HTMLResponse)
    def stage_fragment(stage_id: str, request: Request) -> HTMLResponse:
        provider = registry.provider(stage_id)
        if provider is None:
            raise HTTPException(status_code=404, detail="unknown stage")

        try:
            data = provider.get_data()
        except Exception:  # log details server-side, return a generic message
            logger.exception("Failed to load stage %s", stage_id)
            return templates.TemplateResponse(
                request=request,
                name="stages/_error.html",
                context={
                    "stage": provider.stage,
                    "error": "upstream data could not be loaded",
                },
                status_code=502,
            )

        name = f"stages/{stage_id}.html"
        if not _template_exists(templates, name):
            name = "stages/_generic.html"
        return templates.TemplateResponse(
            request=request,
            name=name,
            context={"stage": provider.stage, "data": data},
        )

    if graph is not None:

        @app.get("/graph/neighborhood", response_class=HTMLResponse)
        def graph_neighborhood(request: Request, ref: str = "", depth: int = 3) -> HTMLResponse:
            ref = ref.strip()
            subgraph = None
            error = None
            if ref:
                try:
                    subgraph = graph.neighborhood(ref, depth=depth)
                except Exception:  # log details server-side, show a generic message
                    logger.exception("Failed to load neighborhood for %s", ref)
                    error = "the graph could not be loaded for that reference"
            return templates.TemplateResponse(
                request=request,
                name="stages/_graph_neighborhood.html",
                context={"ref": ref, "subgraph": subgraph, "error": error},
            )

        @app.get("/graph/referrers", response_class=HTMLResponse)
        def graph_referrers(request: Request, ref: str = "", depth: int = 3) -> HTMLResponse:
            ref = ref.strip()
            subgraph = None
            error = None
            if ref:
                try:
                    subgraph = graph.referrers(ref, depth=depth)
                except Exception:  # log details server-side, show a generic message
                    logger.exception("Failed to load referrers for %s", ref)
                    error = "the referrers could not be loaded for that reference"
            return templates.TemplateResponse(
                request=request,
                name="stages/_graph_referrers.html",
                context={"ref": ref, "subgraph": subgraph, "error": error},
            )

