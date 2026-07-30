from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import (
    analytics_routes,
    auth_routes,
    meal_routes,
    online_learning_routes,
    recipe_routes,
    sustainability_routes,
    user_routes,
    vision_routes,
)
from backend.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="NutriFlavorOS API",
    version="0.2.0",
    description=(
        "Experimental meal-planning API. Outputs are not medical advice and "
        "must not be represented as clinically validated."
    ),
    lifespan=lifespan,
)


def _cors_origins() -> list[str]:
    configured = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
def read_root():
    return {
        "message": "NutriFlavorOS API",
        "status": "experimental",
        "medical_use": "not_clinically_validated",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(meal_routes.router)
app.include_router(analytics_routes.router)
app.include_router(recipe_routes.router)
app.include_router(vision_routes.router)
app.include_router(sustainability_routes.router)
app.include_router(online_learning_routes.router)


FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def serve_frontend(frontend_path: str):
        if frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        requested = (FRONTEND_DIST / frontend_path).resolve()
        if requested.is_file() and FRONTEND_DIST.resolve() in requested.parents:
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
