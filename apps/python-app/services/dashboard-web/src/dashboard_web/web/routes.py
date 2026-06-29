"""HTTP routes for dashboard-web.

The full page (`GET /`) renders one section per registered stage; each section
lazily loads its body from `GET /stages/{id}/fragment` via htmx. A stage with a
dedicated template (`templates/stages/<id>.html`) uses it; otherwise a generic
fallback renders the raw data.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound

from ..stages.base import StageRegistry


def _template_exists(templates: Jinja2Templates, name: str) -> bool:
    try:
        templates.get_template(name)
        return True
    except TemplateNotFound:
        return False


def add_routes(
    app: FastAPI, registry: StageRegistry, templates: Jinja2Templates
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
        except Exception as exc:  # surface upstream failures in the fragment
            return templates.TemplateResponse(
                request=request,
                name="stages/_error.html",
                context={"stage": provider.stage, "error": str(exc)},
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
