"""
ProductMind AI — API v1 Central Router
Aggregates modular endpoint routers into the primary /api/v1 namespace.
"""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    health,
    auth,
    workspaces,
    ai,
    feedback_ai,
    feature_ai,
    prioritization_ai,
    planning_ai,
    orchestrator_ai,
)

api_router = APIRouter()

# Health & Status Endpoint
api_router.include_router(health.router)

# Authentication & Session Management
api_router.include_router(auth.router)

# Workspace Management
api_router.include_router(workspaces.router)

# AI & LLM Foundation Diagnostics
api_router.include_router(ai.router)

# AI Feedback Intelligence Specialist Agent
api_router.include_router(feedback_ai.router)

# AI Feature Intelligence Specialist Agent
api_router.include_router(feature_ai.router)

# AI Prioritization Specialist Agent
api_router.include_router(prioritization_ai.router)

# AI Product Planning Specialist Agent
api_router.include_router(planning_ai.router)

# Central AI Orchestrator (available at /api/v1/ai/orchestrator and /api/v1/orchestrator)
api_router.include_router(orchestrator_ai.router)
api_router.include_router(orchestrator_ai.alias_router)

