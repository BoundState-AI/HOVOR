from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from hovor import __version__
from hovor.api.routes import router
from hovor.content.loader import load_content
from hovor.core.db import init_db

WEB_DIR = Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    app = FastAPI(
        title="HOVOR! backend",
        version=__version__,
        description="Adaptive Slovak language learning platform — Build 1 vertical slice.",
    )
    app.include_router(router)
    app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/app/")

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
