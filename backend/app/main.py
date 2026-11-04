"""
ProductMind AI — FastAPI Application Entry Point
Phase 2, Step 1: Base Application Initialization, Metadata, CORS, and Modular Routing.
"""

from typing import Dict, Any
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import api_router


def create_application() -> FastAPI:
    """Factory creating and configuring the primary FastAPI application instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
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
            "openapi": f"{settings.API_V1_STR}/openapi.json",
        }

    return app


app = create_application()
