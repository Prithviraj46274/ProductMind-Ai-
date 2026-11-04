"""
ProductMind AI — Health Check Endpoint
Provides liveness verification for load balancers, monitoring, and frontend connectivity checks.
"""

from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, status

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Returns the operational status, application name, version, and current server timestamp.",
    response_model=Dict[str, Any],
)
async def check_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
