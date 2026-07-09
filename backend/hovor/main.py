import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from hovor import __version__
from hovor.api.routes import router
from hovor.content.loader import load_content
from hovor.core.db import init_db

WEB_DIR = Path(__file__).resolve().parent / "web"


def _normalize_base_path(raw: str) -> str:
    raw = raw.strip()
    if not raw or raw == "/":
        return ""
    return "/" + raw.strip("/")


def create_app(public_base_path: str | None = None) -> FastAPI:
    """public_base_path: URL prefix when reverse-proxied (e.g. /hovor at
    boundstate.ai/hovor). Defaults to $PUBLIC_BASE_PATH; empty = served at /."""
    base_path = _normalize_base_path(
        public_base_path if public_base_path is not None else os.environ.get("PUBLIC_BASE_PATH", "")
    )
    app = FastAPI(
        title="HOVOR! backend",
        version=__version__,
        description="Adaptive Slovak language learning platform — Build 1 vertical slice.",
        root_path=base_path,
    )
    app.include_router(router)
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")

    # The boundstate.ai Vercel rewrite forwards the prefix verbatim (it does
    # not strip it). Starlette ≥1.x strips root_path during route matching,
    # so marking prefixed requests with root_path — NOT rewriting the path —
    # makes both /hovor/... (proxied) and bare /... (Railway health checks)
    # resolve. Servers like uvicorn preset root_path="", so this must be
    # per-request middleware; the constructor root_path only feeds docs URLs.
    if base_path:
        @app.middleware("http")
        async def apply_base_path(request: Request, call_next):
            path = request.scope["path"]
            if path == base_path:
                return RedirectResponse(url=f"{base_path}/app/")
            if path.startswith(base_path + "/"):
                request.scope["root_path"] = base_path
            return await call_next(request)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url=f"{base_path}/app/")

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        load_content()

    @app.get("/health")
    def health() -> dict:
        content = load_content()
        return {
            "status": "ok",
            "version": __version__,
            "content_version": content.content_version,
            "content_review_status": content.review_status,
        }

    return app


app = create_app()
