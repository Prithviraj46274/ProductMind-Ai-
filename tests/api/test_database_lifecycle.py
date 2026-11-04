"""
ProductMind AI — FastAPI MongoDB Lifecycle & Dependency Injection Tests
Phase 2, Step 2 Verification.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.main import app
from app.core.config import settings
from app.api.dependencies import (
    get_user_repository,
    get_workspace_repository,
    get_feature_repository,
)
from app.database.collections import Collections
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.repositories.feature_repository import FeatureRepository


def test_lifespan_startup_and_shutdown():
    """Verify application lifespan initializes and cleans up MongoDB connection."""
    with TestClient(app) as client:
        # Startup ran
        assert hasattr(app.state, "mongo_client")
        assert app.state.mongo_client is not None
        assert hasattr(app.state, "mongo_db")
        assert app.state.mongo_db is not None
        assert app.state.mongo_db.name == settings.DATABASE_NAME

        response = client.get("/api/v1/health/database")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["database"] == settings.DATABASE_NAME

    # Shutdown ran
    assert getattr(app.state, "mongo_client", None) is None
    assert getattr(app.state, "mongo_db", None) is None


def test_database_health_endpoint_connected():
    """Verify GET /api/v1/health/database returns 200 connected."""
    with TestClient(app) as client:
        response = client.get("/api/v1/health/database")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "connected"
        assert payload["database"] == settings.DATABASE_NAME
        # Ensure credentials / URI are NOT exposed
        assert "mongodb://" not in str(payload)
        assert "password" not in str(payload)


def test_database_health_endpoint_disconnected_handling():
    """Verify GET /api/v1/health/database returns 503 when connection is absent."""
    with TestClient(app) as client:
        # Simulate disconnected state
        original_db = getattr(app.state, "mongo_db", None)
        try:
            app.state.mongo_db = None
            response = client.get("/api/v1/health/database")
            assert response.status_code == 503
            payload = response.json()
            assert payload["detail"]["status"] == "disconnected"
            assert payload["detail"]["database"] == settings.DATABASE_NAME
        finally:
            app.state.mongo_db = original_db


def test_database_collections_endpoint():
    """Verify GET /api/v1/health/database/collections lists accessible collections without leaking records."""
    with TestClient(app) as client:
        response = client.get("/api/v1/health/database/collections")
        assert response.status_code == 200
        payload = response.json()
        assert payload["database"] == settings.DATABASE_NAME
        assert payload["total_expected"] == 23
        assert payload["accessible_count"] >= 19
        assert payload["repository_verified"] is True
        assert len(payload["collections"]) == 23

        # Verify no customer data or user details leaked
        serialized = str(payload).lower()
        assert "alex.rivera" not in serialized
        assert "passwordhash" not in serialized
        assert "feedbackitems" not in serialized


def test_dependency_injection_mongo_client_and_db():
    """Verify get_mongo_client and get_mongo_db dependencies resolve active connection."""
    with TestClient(app):
        assert getattr(app.state, "mongo_client", None) is not None
        assert getattr(app.state, "mongo_db", None) is not None


@pytest.mark.asyncio
async def test_repository_dependency_injection(async_db):
    """Verify domain repositories are instantiated correctly through dependencies and query data."""
    # async_db fixture provides the AsyncIOMotorDatabase bound to the test's event loop
    user_repo = get_user_repository(async_db)
    assert isinstance(user_repo, UserRepository)
    assert user_repo.collection_name == Collections.USERS

    workspace_repo = get_workspace_repository(async_db)
    assert isinstance(workspace_repo, WorkspaceRepository)
    assert workspace_repo.collection_name == Collections.WORKSPACES

    feature_repo = get_feature_repository(async_db)
    assert isinstance(feature_repo, FeatureRepository)
    assert feature_repo.collection_name == Collections.FEATURES

    # Verify repository read operation through injected dependency
    demo_user = await user_repo.find_by_email("alex.rivera@productmind.ai")
    assert demo_user is not None
    assert demo_user.email == "alex.rivera@productmind.ai"
    assert demo_user.name == "Alex Rivera"
