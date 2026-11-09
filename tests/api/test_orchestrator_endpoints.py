"""
ProductMind AI — AI Orchestrator API Endpoints Tests
Tests:
- POST /api/v1/ai/orchestrator/run (authenticated success, unauthenticated 401, forbidden 403, dependency error 422)
- GET /api/v1/ai/orchestrator/runs/{run_id} (authenticated success, 404 not found, 403 forbidden)
- GET /api/v1/ai/orchestrator/health (operational diagnostic 200)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user, get_mongo_db
from app.api.v1.endpoints.orchestrator_ai import get_ai_orchestrator
from app.ai.orchestrator.exceptions import (
    OrchestratorAuthorizationException,
    OrchestratorDependencyException,
    OrchestratorValidationException,
)
from app.ai.orchestrator.schemas import (
    OrchestratorHealthResponse,
    OrchestratorRequest,
    OrchestratorResponse,
    PipelineMode,
    PipelineStatus,
    StageResult,
    StageStatus,
    StageType,
)
from app.models.auth import User
from app.core.enums import PlatformRole

client = TestClient(app)

MOCK_USER_ID = ObjectId("660011223344556677889901")
MOCK_WS_ID = "660011223344556677889902"
MOCK_RUN_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Ensure clean dependency override state before and after each test."""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_mongo_db] = lambda: MagicMock()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_auth_user():
    return User(
        id=MOCK_USER_ID,
        name="Lead PM",
        email="lead.pm@productmind.ai",
        password_hash="mock_hash",
        platform_role=PlatformRole.USER,
        is_active=True,
    )


@pytest.fixture
def sample_orchestrator_response():
    now = datetime.now(timezone.utc)
    return OrchestratorResponse(
        run_id=MOCK_RUN_ID,
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        status=PipelineStatus.COMPLETED,
        stages=[
            StageResult(
                stage=StageType.FEEDBACK_INTELLIGENCE,
                status=StageStatus.COMPLETED,
                started_at=now,
                completed_at=now,
                duration_ms=120.0,
            ),
            StageResult(
                stage=StageType.FEATURE_INTELLIGENCE,
                status=StageStatus.COMPLETED,
                started_at=now,
                completed_at=now,
                duration_ms=250.0,
            ),
            StageResult(
                stage=StageType.PRIORITIZATION,
                status=StageStatus.COMPLETED,
                started_at=now,
                completed_at=now,
                duration_ms=180.0,
            ),
            StageResult(
                stage=StageType.PRODUCT_PLANNING,
                status=StageStatus.COMPLETED,
                started_at=now,
                completed_at=now,
                duration_ms=450.0,
            ),
        ],
        started_at=now,
        completed_at=now,
        total_duration_ms=1000.0,
    )


# --------------------------------------------------------------------------
# Authentication & Authorization Tests
# --------------------------------------------------------------------------
def test_run_pipeline_unauthenticated():
    """Unauthenticated request to /run returns 401."""
    payload = {
        "workspace_id": MOCK_WS_ID,
        "mode": "full",
    }
    response = client.post("/api/v1/ai/orchestrator/run", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_run_unauthenticated():
    """Unauthenticated request to /runs/{run_id} returns 401."""
    response = client.get(f"/api/v1/ai/orchestrator/runs/{MOCK_RUN_ID}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_health_check_unauthenticated_accessible():
    """Health check is open or accessible for diagnostics."""
    mock_orchestrator = MagicMock()
    mock_orchestrator.get_health = AsyncMock(
        return_value=OrchestratorHealthResponse(
            status="healthy",
            healthy=True,
            active_runs_cached=0,
            uptime_seconds=100.0,
            specialist_agents=[],
        )
    )
    app.dependency_overrides[get_ai_orchestrator] = lambda: mock_orchestrator

    response = client.get("/api/v1/ai/orchestrator/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"


# --------------------------------------------------------------------------
# Pipeline Execution Endpoint Tests
# --------------------------------------------------------------------------
def test_run_pipeline_success(mock_auth_user, sample_orchestrator_response):
    """POST /run executes pipeline and returns full OrchestratorResponse."""
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_pipeline = AsyncMock(return_value=sample_orchestrator_response)
    app.dependency_overrides[get_ai_orchestrator] = lambda: mock_orchestrator

    payload = {
        "workspace_id": MOCK_WS_ID,
        "mode": "full",
        "feedback_ids": ["660011223344556677889911"],
    }
    response = client.post("/api/v1/ai/orchestrator/run", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["run_id"] == MOCK_RUN_ID
    assert data["status"] == "completed"
    assert len(data["stages"]) == 4


def test_run_pipeline_forbidden_workspace(mock_auth_user):
    """POST /run with unauthorized workspace returns 403."""
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_pipeline = AsyncMock(
        side_effect=OrchestratorAuthorizationException("User is not a member of workspace.")
    )
    app.dependency_overrides[get_ai_orchestrator] = lambda: mock_orchestrator

    payload = {
        "workspace_id": "660011223344556677889999",
        "mode": "full",
    }
    response = client.post("/api/v1/ai/orchestrator/run", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "not a member" in response.json()["detail"]


def test_run_pipeline_dependency_error(mock_auth_user):
    """POST /run with missing stage prerequisites returns 422."""
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user

    mock_orchestrator = MagicMock()
    mock_orchestrator.run_pipeline = AsyncMock(
        side_effect=OrchestratorDependencyException("Stage requires prerequisite data.")
    )
    app.dependency_overrides[get_ai_orchestrator] = lambda: mock_orchestrator

    payload = {
        "workspace_id": MOCK_WS_ID,
        "mode": "partial",
        "stages": ["feature_intelligence"],
    }
    response = client.post("/api/v1/ai/orchestrator/run", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "prerequisite" in response.json()["detail"]


# --------------------------------------------------------------------------
# Run Retrieval Endpoint Tests
# --------------------------------------------------------------------------
def test_get_run_success(mock_auth_user, sample_orchestrator_response):
    """GET /runs/{run_id} returns cached run state."""
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user

    mock_orchestrator = MagicMock()
    mock_orchestrator.get_run_by_id = AsyncMock(return_value=sample_orchestrator_response)
    app.dependency_overrides[get_ai_orchestrator] = lambda: mock_orchestrator

    response = client.get(f"/api/v1/ai/orchestrator/runs/{MOCK_RUN_ID}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["run_id"] == MOCK_RUN_ID


def test_get_run_not_found(mock_auth_user):
    """GET /runs/{run_id} returns 404 when run does not exist."""
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user

    mock_orchestrator = MagicMock()
    mock_orchestrator.get_run_by_id = AsyncMock(return_value=None)
    app.dependency_overrides[get_ai_orchestrator] = lambda: mock_orchestrator

    response = client.get(f"/api/v1/ai/orchestrator/runs/nonexistent-run-id")
    assert response.status_code == status.HTTP_404_NOT_FOUND
