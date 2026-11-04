"""
ProductMind AI — Health & Database Connectivity Endpoints
Provides system liveness, database connectivity verification, and non-sensitive
collection registry inspection.
"""

from datetime import datetime, timezone
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.api.dependencies import get_mongo_db, get_collections, get_user_repository
from app.database.collections import Collections
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("productmind.api.health")

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Returns the operational status, application name, version, and current server timestamp.",
    response_model=Dict[str, Any],
)
async def check_health() -> Dict[str, Any]:
    """Independent application liveness check (does not require database)."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/health/database",
    status_code=status.HTTP_200_OK,
    summary="Database Health Check",
    description="Pings the active MongoDB instance to verify database reachability using the application's connection pool.",
    response_model=Dict[str, Any],
)
async def check_database_health(
    request: Request,
) -> Dict[str, Any]:
    """
    Verifies that MongoDB is reachable using the application's active connection.
    Does not expose URI, credentials, or internal topology.
    """
    db: AsyncIOMotorDatabase = getattr(request.app.state, "mongo_db", None)
    if db is None:
        logger.warning("Database health check requested but db is not connected.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "disconnected",
                "database": settings.DATABASE_NAME,
                "error": "Database service unavailable: connection not established",
            },
        )

    try:
        # Ping database server using active connection
        await db.command("ping")
        return {
            "status": "connected",
            "database": db.name,
        }
    except Exception as exc:
        logger.error("MongoDB ping failed during health check: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "disconnected",
                "database": db.name,
                "error": "Database service unavailable",
            },
        )


@router.get(
    "/health/database/collections",
    status_code=status.HTTP_200_OK,
    summary="Database Collections Accessibility",
    description="Verifies accessibility of registered collections and repository injection without exposing any sensitive or private document records.",
    response_model=Dict[str, Any],
)
async def check_database_collections(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    collections_registry: type[Collections] = Depends(get_collections),
    user_repo: UserRepository = Depends(get_user_repository),
) -> Dict[str, Any]:
    """
    Demonstrates repository dependency injection and collection registry verification.
    Strictly read-only and metadata-focused: does not return user records, feedback, or credentials.
    """
    try:
        active_collections = set(await db.list_collection_names())
        all_expected: List[str] = collections_registry.all_collections()

        collection_status = []
        accessible_count = 0
        for col_name in sorted(all_expected):
            is_present = col_name in active_collections
            if is_present:
                accessible_count += 1
            collection_status.append({
                "name": col_name,
                "accessible": is_present,
            })

        # Demonstrate repository access through dependency injection safely
        repo_collection_accessible = user_repo.collection_name in active_collections

        return {
            "database": db.name,
            "total_expected": len(all_expected),
            "accessible_count": accessible_count,
            "repository_verified": repo_collection_accessible,
            "collections": collection_status,
        }
    except Exception as exc:
        logger.error("Failed to inspect collection statuses: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "database": db.name if db is not None else settings.DATABASE_NAME,
                "error": "Failed to inspect database collections",
            },
        )
