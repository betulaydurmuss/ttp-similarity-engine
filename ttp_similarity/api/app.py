"""HTTP surface of the station.

Run::

    python -m ttp_similarity.api                 # http://127.0.0.1:8000
    python -m ttp_similarity.api --host 0.0.0.0  # inside Docker

``/api/*`` serves JSON; everything else serves the built interface from
``web/dist``. The interactive API reference lives at ``/api/docs``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .. import __version__, paths
from .service import MAX_QUERY_TECHNIQUES, Station, UnknownActorError

WEB_DIST: Path = paths.PROJECT_ROOT / "web" / "dist"
ACTOR_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'"
)


class QueryRequest(BaseModel):
    techniques: list[Annotated[str, Field(max_length=40)]] | Annotated[str, Field(max_length=16_000)]
    top_k: int = Field(default=10, ge=1, le=50)

    @field_validator("techniques")
    @classmethod
    def bounded(cls, value: Any) -> Any:
        if isinstance(value, list) and len(value) > MAX_QUERY_TECHNIQUES:
            raise ValueError(f"at most {MAX_QUERY_TECHNIQUES} techniques per query")
        return value


class NoiseRequest(BaseModel):
    techniques: list[Annotated[str, Field(max_length=40)]] = Field(max_length=MAX_QUERY_TECHNIQUES)
    ratio: float = Field(default=0.3, gt=0.0, le=1.0)
    seed: int | None = None


class BlindRequest(BaseModel):
    fraction: float = Field(default=0.4, gt=0.0, le=1.0)
    noise_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    seed: int | None = None


def create_app(station: Station | None = None, *, dataset: str | None = None,
               web_dist: Path | None = WEB_DIST) -> FastAPI:
    """Build the application around a station (loaded from disk when omitted)."""
    station = station or Station.from_workspace(dataset)
    app = FastAPI(
        title="TTP Benzerlik İstasyonu",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.station = station

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if not request.url.path.startswith("/api/docs"):
            response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "dataset": station.artifacts.dataset}

    @app.get("/api/station")
    def overview() -> dict[str, Any]:
        return station.overview()

    @app.post("/api/query")
    def run_query(body: QueryRequest) -> dict[str, Any]:
        return station.query(body.techniques, top_k=body.top_k)

    @app.get("/api/actors/{actor_id}")
    def dossier(actor_id: Annotated[str, PathParam(pattern=ACTOR_ID_PATTERN)]) -> dict[str, Any]:
        try:
            return station.dossier(actor_id)
        except UnknownActorError:
            raise HTTPException(status_code=404, detail="Bu kimlikte bir aktör yok.") from None

    @app.get("/api/compare")
    def compare(
        a: Annotated[str, Query(pattern=ACTOR_ID_PATTERN)],
        b: Annotated[str, Query(pattern=ACTOR_ID_PATTERN)],
    ) -> dict[str, Any]:
        try:
            return station.compare(a, b)
        except UnknownActorError:
            raise HTTPException(status_code=404, detail="Aktörlerden biri bulunamadı.") from None

    @app.post("/api/noise")
    def noise(body: NoiseRequest) -> dict[str, list[str]]:
        return {"noise": station.noise(body.techniques, body.ratio, body.seed)}

    @app.post("/api/blind")
    def blind(body: BlindRequest) -> dict[str, Any]:
        return station.blind_case(body.fraction, body.noise_ratio, body.seed)

    @app.get("/api/trust")
    def trust() -> dict[str, Any]:
        return station.trust()

    @app.exception_handler(404)
    async def not_found(request: Request, exc: Exception):
        if request.url.path.startswith("/api/") or web_dist is None:
            detail = getattr(exc, "detail", "Bulunamadı.")
            return JSONResponse({"detail": detail}, status_code=404)
        index = web_dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Arayüz derlenmemiş: cd web && npm run build"}, status_code=404)

    if web_dist is not None and (web_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app
