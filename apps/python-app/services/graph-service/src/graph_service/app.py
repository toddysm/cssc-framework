"""FastAPI application exposing the supply-chain-graph query journeys.

The service owns a single LadybugDB writer (:class:`GraphIndex`), rebuilds it from
the committed data root on startup, and serves read-only queries that reuse the
shared ``cssc_graph.queries`` layer (the same code the ``cssc-graph`` CLI uses).
Every query runs inside the index read guard so a rebuild never closes the store
mid-request.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Iterator

from cssc_graph import queries
from cssc_graph.graph import GraphStore
from fastapi import FastAPI, HTTPException, Query, Response

from . import __version__
from .config import GraphSettings, graph_settings
from .indexing import GraphIndex, GraphNotReady, IndexingError

logger = logging.getLogger(__name__)


def create_app(settings: GraphSettings | None = None, index: GraphIndex | None = None) -> FastAPI:
    settings = settings or graph_settings()
    index = index or GraphIndex(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            index.rebuild()
        except IndexingError:
            logger.exception("startup index failed; service will report not-ready")
        except Exception:  # pragma: no cover - defensive; keep the pod alive for /healthz
            logger.exception("unexpected error building the graph on startup")
        yield
        index.close()

    app = FastAPI(title="graph-service", version=__version__, lifespan=lifespan)
    app.state.index = index
    app.state.settings = settings

    @contextmanager
    def reading() -> Iterator[GraphStore]:
        try:
            with index.reading() as store:
                yield store
        except GraphNotReady as exc:
            raise HTTPException(status_code=503, detail="graph index not ready") from exc

    def clamp_depth(depth: int) -> int:
        return max(1, min(depth, settings.max_depth))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        if not index.ready:
            raise HTTPException(status_code=503, detail="graph index not ready")
        return {"status": "ready", **index.as_dict()}

    @app.post("/index/rebuild")
    def rebuild() -> dict[str, Any]:
        try:
            index.rebuild()
        except IndexingError as exc:
            raise HTTPException(status_code=422, detail=exc.diagnostics) from exc
        return {"status": "ok", **index.as_dict()}

    @app.get("/artifacts/resolve")
    def resolve(
        ref: str | None = Query(None, description="registry/repository[@digest|:tag]"),
        digest: str | None = Query(None, description="sha256:..."),
    ) -> dict[str, Any]:
        if not ref and not digest:
            raise HTTPException(status_code=400, detail="provide ref or digest")
        with reading() as store:
            return {"occurrences": queries.resolve_seed(store, digest=digest, ref=ref)}

    @app.get("/artifacts/path")
    def artifact_path(
        ref: str | None = Query(None),
        digest: str | None = Query(None),
        depth: int = Query(queries.DEFAULT_DEPTH, ge=1),
    ) -> dict[str, Any]:
        if not ref and not digest:
            raise HTTPException(status_code=400, detail="provide ref or digest")
        with reading() as store:
            return queries.path(store, digest=digest, ref=ref, depth=clamp_depth(depth))

    @app.get("/artifacts/bases")
    def artifact_bases(ref: str = Query(...), depth: int = Query(queries.DEFAULT_DEPTH, ge=1)) -> dict[str, Any]:
        with reading() as store:
            return queries.bases(store, ref, depth=clamp_depth(depth))

    @app.get("/artifacts/derived")
    def artifact_derived(base: str = Query(...), depth: int = Query(queries.DEFAULT_DEPTH, ge=1)) -> dict[str, Any]:
        with reading() as store:
            return queries.derived(store, base, depth=clamp_depth(depth))

    @app.get("/artifacts/show")
    def artifact_show(ref: str = Query(...)) -> dict[str, Any]:
        with reading() as store:
            result = queries.show(store, ref)
        if result is None:
            raise HTTPException(status_code=404, detail=f"no occurrence for '{ref}'")
        return result

    @app.get("/artifacts/referrers")
    def artifact_referrers(
        ref: str | None = Query(None),
        digest: str | None = Query(None),
        depth: int = Query(3, ge=0),
        format: str = Query("json", pattern="^(json|cytoscape|mermaid)$"),
    ) -> Any:
        if not ref and not digest:
            raise HTTPException(status_code=400, detail="provide ref or digest")
        with reading() as store:
            subgraph = queries.referrers(
                store, digest=digest, ref=ref, depth=min(depth, settings.max_depth)
            )
        if format == "cytoscape":
            return queries.to_cytoscape(subgraph)
        if format == "mermaid":
            return Response(content=queries.to_mermaid(subgraph), media_type="text/plain")
        return subgraph

    @app.get("/repositories/tags/history")
    def tag_history(ref: str = Query(...), tag: str = Query(...)) -> dict[str, Any]:
        with reading() as store:
            return {"observations": queries.tag_history(store, ref, tag)}

    @app.get("/search")
    def search(
        annotation: str | None = Query(None, description="name=value"),
        artifact_type: str | None = Query(None, alias="type", description="mediaType or artifactType"),
        ref: str | None = Query(None),
    ) -> dict[str, Any]:
        try:
            with reading() as store:
                results = queries.find(store, annotation=annotation, artifact_type=artifact_type, ref=ref)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"results": results}

    @app.get("/graph/neighborhood")
    def neighborhood(
        ref: str | None = Query(None),
        digest: str | None = Query(None),
        depth: int = Query(queries.DEFAULT_DEPTH, ge=1),
        format: str = Query("json", pattern="^(json|cytoscape|mermaid)$"),
    ) -> Any:
        if not ref and not digest:
            raise HTTPException(status_code=400, detail="provide ref or digest")
        with reading() as store:
            subgraph = queries.path(store, digest=digest, ref=ref, depth=clamp_depth(depth))
        if format == "cytoscape":
            return queries.to_cytoscape(subgraph)
        if format == "mermaid":
            return Response(content=queries.to_mermaid(subgraph), media_type="text/plain")
        return subgraph

    return app


app = create_app()
