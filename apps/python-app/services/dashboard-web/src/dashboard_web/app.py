"""FastAPI application for dashboard-web."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .clients import IssuesServiceClient, PackagesServiceClient
from .config import DashboardSettings, dashboard_settings
from .stages.acquisition import AcquisitionProvider
from .stages.base import StageRegistry
from .web.routes import add_routes

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def build_registry(settings: DashboardSettings) -> StageRegistry:
    """Construct the default stage registry from settings.

    New stages are registered here; the rest of the app is stage-agnostic.
    """

    packages = PackagesServiceClient(settings.packages_service_url)
    issues = IssuesServiceClient(settings.issues_service_url)

    registry = StageRegistry()
    registry.register(
        AcquisitionProvider(
            packages,
            issues,
            namespace=settings.quarantine_namespace,
            cve_base_url=settings.cve_base_url,
        )
    )
    return registry


def create_app(
    registry: StageRegistry | None = None,
    settings: DashboardSettings | None = None,
) -> FastAPI:
    settings = settings or dashboard_settings()
    registry = registry or build_registry(settings)

    app = FastAPI(title="dashboard-web", version="0.1.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    add_routes(app, registry, templates)
    return app


app = create_app()
