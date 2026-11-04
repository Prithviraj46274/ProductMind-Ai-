"""
ProductMind AI — API v1 Central Router
Aggregates modular endpoint routers into the primary /api/v1 namespace.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import health, auth

api_router = APIRouter()

# Health & Status Endpoint
api_router.include_router(health.router)

# Authentication & Session Management
api_router.include_router(auth.router)
