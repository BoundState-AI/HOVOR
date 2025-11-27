"""RouteIntel FastAPI application.

Main application entry point with route registration and web UI.
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from routeintel.core.config import get_settings
from routeintel.core.db import init_db
from routeintel.core.logging import setup_logging
from routeintel.api.routes_trips import router as trips_router
from routeintel.api.routes_companies import router as companies_router

settings = get_settings()
setup_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

init_db()

app.mount("/static", StaticFiles(directory="routeintel/web/static"), name="static")
templates = Jinja2Templates(directory="routeintel/web/templates")

app.include_router(trips_router, prefix=settings.api_v1_prefix)
app.include_router(companies_router, prefix=settings.api_v1_prefix)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
