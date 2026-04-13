"""FastAPI application factory."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.deps import get_settings
from api.routes import leads, pipeline, email, export, agents


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SalesLeads API", version="1.0.0", redirect_slashes=True)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(leads.router)
    app.include_router(pipeline.router)
    app.include_router(email.router)
    app.include_router(export.router)
    app.include_router(agents.router)

    # Serve frontend static files in production
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


app = create_app()
