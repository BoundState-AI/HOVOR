from fastapi import FastAPI

from hovor import __version__
from hovor.api.routes import router
from hovor.content.loader import load_content
from hovor.core.db import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="HOVOR! backend",
        version=__version__,
        description="Adaptive Slovak language learning platform — Build 1 vertical slice.",
    )
    app.include_router(router)

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
