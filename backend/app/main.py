"""
ProductMind AI — FastAPI Application Entry Point
Phase 2, Step 2: Lifecycle Management (Lifespan Context), MongoDB Integration,
CORS, and Modular Routing.
"""

from contextlib import asynccontextmanager
import logging
from typing import Dict, Any, AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.connection import MongoDBManager
from app.api.v1 import api_router

logger = logging.getLogger("productmind.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manages application startup and shutdown lifecycle.
    Initializes and verifies the MongoDB connection on startup,
    and cleanly closes connection pools on shutdown.
    """
    # -------------------------------------------------------------------------
    # Application Startup
    # -------------------------------------------------------------------------
    logger.info("Starting up %s (v%s)...", settings.PROJECT_NAME, settings.VERSION)
    try:
        db = await MongoDBManager.connect_async(settings.MONGODB_URI)
        app.state.mongo_client = MongoDBManager._async_client
        app.state.mongo_db = db
        logger.info("Connected to MongoDB successfully. Target database: [%s]", db.name)
    except Exception as exc:
        logger.error("Failed to connect to MongoDB during startup: %s", exc)
        app.state.mongo_client = None
        app.state.mongo_db = None

    yield

    # -------------------------------------------------------------------------
    # Application Shutdown
    # -------------------------------------------------------------------------
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    try:
        await MongoDBManager.close_async()
        app.state.mongo_client = None
        app.state.mongo_db = None
        logger.info("MongoDB connection closed gracefully.")
    except Exception as exc:
        logger.error("Error closing MongoDB connection: %s", exc)


def create_application() -> FastAPI:
    """Factory creating and configuring the primary FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 Modular Router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get(
        "/",
        tags=["Root"],
        summary="API Root Information",
        status_code=status.HTTP_200_OK,
        response_model=Dict[str, Any],
    )
    async def root() -> Dict[str, Any]:
        """Root endpoint providing service metadata and discovery links."""
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": "/docs",
            "health": f"{settings.API_V1_STR}/health",
            "database_health": f"{settings.API_V1_STR}/health/database",
            "ai_health": f"{settings.API_V1_STR}/ai/health",
            "openapi": f"{settings.API_V1_STR}/openapi.json",
        }

    return app


app = create_application()
