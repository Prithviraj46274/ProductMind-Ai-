"""
ProductMind AI — API v1 Central Router
Aggregates modular endpoint routers into the primary /api/v1 namespace.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, ai, feedback_ai, feature_ai

api_router = APIRouter()

# Health & Status Endpoint
api_router.include_router(health.router)

# Authentication & Session Management
api_router.include_router(auth.router)

# AI & LLM Foundation Diagnostics
api_router.include_router(ai.router)

# AI Feedback Intelligence Specialist Agent
api_router.include_router(feedback_ai.router)

# AI Feature Intelligence Specialist Agent
api_router.include_router(feature_ai.router)
