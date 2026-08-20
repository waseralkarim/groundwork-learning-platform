"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    attainment,
    auth,
    authoring,
    curriculum,
    health,
    internal,
    learning,
    meta,
    projects,
    search,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(curriculum.router)
api_router.include_router(learning.router)
api_router.include_router(search.router)
api_router.include_router(attainment.router)
api_router.include_router(projects.router)
# Admin-only. Reads the content tree and reports on it; the one mutation is a
# re-ingest, which refuses invalid content.
api_router.include_router(authoring.router)
api_router.include_router(authoring.protected)
# Blocked at the edge — see the Caddyfile and app/api/v1/internal.py.
api_router.include_router(internal.router)
