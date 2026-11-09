"""
ProductMind AI — Prioritization API Endpoints Integration Tests
Tests POST /api/v1/ai/prioritization/analyze, GET /api/v1/ai/prioritization/results,
GET /api/v1/ai/prioritization/results/{id}, and POST /api/v1/ai/prioritization/rank.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user, get_mongo_db
from app.api.v1.endpoints.prioritization_ai import get_prioritization_service
from app.ai.agents.prioritization import (
    AnalyzePrioritizationResponse,
    PrioritizationResult,
    PriorityLevel,
    RankPrioritizationResponse,
)
from app.ai.exceptions import (
    AIRateLimitException,
    AITimeoutException,
    AIAuthenticationException,
    AIProviderException,
)
from app.models.auth import User
from app.core.enums import PlatformRole

client = TestClient(app)

MOCK_USER_ID = ObjectId("660011223344556677889901")
MOCK_WS_ID = "660011223344556677889902"
MOCK_RESULT_ID = "660011223344556677889903"
MOCK_GROUP_ID = "660011223344556677889904"


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Ensure clean dependency override state before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_auth_user():
    return User(
        id=MOCK_USER_ID,
        name="Lead PM",
        email="lead.pm@productmind.ai",
        password_hash="mock_bcrypt_hash",
        platform_role=PlatformRole.USER,
        is_active=True,
    )


@pytest.fixture
def sample_prioritization_result():
    return PrioritizationResult(
        result_id=MOCK_RESULT_ID,
        workspace_id=MOCK_WS_ID,
        feature_group_id=MOCK_GROUP_ID,
        group_name="Dark Mode Theme Support",
        final_score=84.5,
        priority_level=PriorityLevel.CRITICAL,
        factor_scores={
            "customer_demand": 80.0,
            "urgency": 75.0,
            "business_impact": 85.0,
            "strategic_alignment": 90.0,
            "sentiment": 90.0,
            "usage_impact": 80.0,
        },
        factor_weights={
            "customer_demand": 0.25,
            "urgency": 0.20,
            "business_impact": 0.20,
            "strategic_alignment": 0.15,
            "sentiment": 0.10,
            "usage_impact": 0.10,
        },
        coverage_percentage=100.0,
        explanation="High customer demand and strategic alignment drive critical priority score.",
        customer_pain_point_severity="Severe nighttime eye strain",
        implementation_benefits=["Reduces visual fatigue", "Improves session duration"],
        delay_risks=["User churn to competitors"],
        supporting_evidence=["Working late at night is blinding"],
        missing_data=[],
        recommendation="Immediate sprint priority.",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# -------------------------------------------------------------------------
# 1. Unauthenticated Endpoint Tests (Must Return 401)
# -------------------------------------------------------------------------

def test_analyze_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    res = client.post(
        "/api/v1/ai/prioritization/analyze",
        json={"workspace_id": MOCK_WS_ID},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_results_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    res = client.get(f"/api/v1/ai/prioritization/results?workspace_id={MOCK_WS_ID}")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_result_by_id_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    res = client.get(f"/api/v1/ai/prioritization/results/{MOCK_RESULT_ID}?workspace_id={MOCK_WS_ID}")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_rank_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    res = client.post(
        "/api/v1/ai/prioritization/rank",
        json={"workspace_id": MOCK_WS_ID},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED



# -------------------------------------------------------------------------
# 2. Authenticated Happy-Path Tests (Return 200 OK)
# -------------------------------------------------------------------------

def test_analyze_prioritization_success(mock_auth_user, sample_prioritization_result):
    mock_service = MagicMock()
    mock_service.analyze_prioritization = AsyncMock(
        return_value=AnalyzePrioritizationResponse(
            workspace_id=MOCK_WS_ID,
            total_evaluated=1,
            results=[sample_prioritization_result],
            execution_metadata={"total_evaluated": 1, "elapsed_ms": 120.5},
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.post(
        "/api/v1/ai/prioritization/analyze",
        json={
            "workspace_id": MOCK_WS_ID,
            "force_reanalyze": False,
        },
    )

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["workspace_id"] == MOCK_WS_ID
    assert data["total_evaluated"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["final_score"] == 84.5
    assert data["results"][0]["priority_level"] == "Critical"


def test_list_prioritization_results_success(mock_auth_user, sample_prioritization_result):
    mock_service = MagicMock()
    mock_service.get_prioritization_results = AsyncMock(return_value=[sample_prioritization_result])

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.get(f"/api/v1/ai/prioritization/results?workspace_id={MOCK_WS_ID}")

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["result_id"] == MOCK_RESULT_ID


def test_get_prioritization_result_by_id_success(mock_auth_user, sample_prioritization_result):
    mock_service = MagicMock()
    mock_service.get_prioritization_result_by_id = AsyncMock(return_value=sample_prioritization_result)

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.get(f"/api/v1/ai/prioritization/results/{MOCK_RESULT_ID}?workspace_id={MOCK_WS_ID}")

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["result_id"] == MOCK_RESULT_ID
    assert data["group_name"] == "Dark Mode Theme Support"


def test_rank_features_success(mock_auth_user, sample_prioritization_result):
    mock_service = MagicMock()
    mock_service.rank_feature_groups = AsyncMock(
        return_value=RankPrioritizationResponse(
            workspace_id=MOCK_WS_ID,
            total_ranked=1,
            ranked_results=[sample_prioritization_result],
            summary="Ranked 1 feature groups: 1 Critical, 0 High, 0 Medium, 0 Low.",
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.post(
        "/api/v1/ai/prioritization/rank",
        json={
            "workspace_id": MOCK_WS_ID,
            "top_k": 5,
        },
    )

    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total_ranked"] == 1
    assert len(data["ranked_results"]) == 1
    assert data["ranked_results"][0]["priority_level"] == "Critical"


# -------------------------------------------------------------------------
# 3. Workspace Authorization Failure (Must Return 403)
# -------------------------------------------------------------------------

def test_analyze_workspace_forbidden(mock_auth_user):
    mock_service = MagicMock()
    mock_service.analyze_prioritization = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have active access to this workspace",
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.post(
        "/api/v1/ai/prioritization/analyze",
        json={"workspace_id": MOCK_WS_ID},
    )

    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "access" in res.json()["detail"].lower()


# -------------------------------------------------------------------------
# 4. Error Mapping Tests (429 RateLimit, 504 Timeout, 502 Bad Gateway)
# -------------------------------------------------------------------------

def test_analyze_rate_limit_error(mock_auth_user):
    mock_service = MagicMock()
    mock_service.analyze_prioritization = AsyncMock(
        side_effect=AIRateLimitException("Groq rate limit exceeded", provider="groq")
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.post(
        "/api/v1/ai/prioritization/analyze",
        json={"workspace_id": MOCK_WS_ID},
    )

    assert res.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "rate limit" in res.json()["detail"].lower()


def test_analyze_timeout_error(mock_auth_user):
    mock_service = MagicMock()
    mock_service.analyze_prioritization = AsyncMock(
        side_effect=AITimeoutException("Groq timed out after 60s", provider="groq")
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.post(
        "/api/v1/ai/prioritization/analyze",
        json={"workspace_id": MOCK_WS_ID},
    )

    assert res.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert "timed out" in res.json()["detail"].lower()


def test_analyze_provider_error(mock_auth_user):
    mock_service = MagicMock()
    mock_service.analyze_prioritization = AsyncMock(
        side_effect=AIProviderException("Upstream 503 Service Unavailable", provider="groq")
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_prioritization_service] = lambda: mock_service

    res = client.post(
        "/api/v1/ai/prioritization/analyze",
        json={"workspace_id": MOCK_WS_ID},
    )

    assert res.status_code == status.HTTP_502_BAD_GATEWAY
    assert "failure" in res.json()["detail"].lower()

