"""
ProductMind AI — Feature Intelligence API Endpoints Integration Tests (Step 3)
Tests POST /api/v1/ai/features/group, GET /api/v1/ai/features/groups,
GET /api/v1/ai/features/groups/{id}, and POST /api/v1/ai/features/detect-duplicates.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user, get_mongo_db
from app.api.v1.endpoints.feature_ai import get_feature_intelligence_service
from app.ai.agents.feature_intelligence import (
    FeatureGroupResult,
    GroupFeaturesResponse,
    DuplicateDetectionItem,
    DuplicateDetectionResponse,
    DuplicateType,
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
MOCK_GROUP_ID = "660011223344556677889903"
MOCK_FEEDBACK_ID = "660011223344556677889904"


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
def sample_feature_group_result():
    return FeatureGroupResult(
        feature_group_id=MOCK_GROUP_ID,
        workspace_id=MOCK_WS_ID,
        group_name="Dark Mode Theme Support",
        feature_summary="Introduce toggleable dark mode across all analytics dashboards.",
        consolidated_description="Multiple users requested night mode to prevent eye strain during evening workflows.",
        related_feedback_ids=[MOCK_FEEDBACK_ID, "660011223344556677889905"],
        total_request_count=2,
        unique_customer_count=2,
        sentiment_distribution={"Positive": 1, "Neutral": 0, "Negative": 1, "Mixed": 0},
        urgency_distribution={"Critical": 0, "High": 1, "Medium": 1, "Low": 0},
        common_themes=["UI Customization", "Themes"],
        common_pain_points=["Eye strain in dark environments"],
        evidence=["Working late at night is blinding", "need a night theme"],
        suggested_capability="Dark theme toggle switch",
        grouping_confidence=0.92,
        grouping_reason="Both feedback items request identical dark interface capability.",
        grouping_status="suggested",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# -------------------------------------------------------------------------
# 1. Unauthenticated Endpoint Tests (Must Return 401)
# -------------------------------------------------------------------------

def test_group_features_unauthenticated():
    """Verify POST /api/v1/ai/features/group returns 401 when no auth token is provided."""
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db

    response = client.post(
        "/api/v1/ai/features/group",
        json={"workspace_id": MOCK_WS_ID},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_feature_groups_unauthenticated():
    """Verify GET /api/v1/ai/features/groups returns 401 when unauthenticated."""
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db

    response = client.get(f"/api/v1/ai/features/groups?workspace_id={MOCK_WS_ID}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_feature_group_unauthenticated():
    """Verify GET /api/v1/ai/features/groups/{id} returns 401 when unauthenticated."""
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db

    response = client.get(f"/api/v1/ai/features/groups/{MOCK_GROUP_ID}?workspace_id={MOCK_WS_ID}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_detect_duplicates_unauthenticated():
    """Verify POST /api/v1/ai/features/detect-duplicates returns 401 when unauthenticated."""
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db

    response = client.post(
        "/api/v1/ai/features/detect-duplicates",
        json={"workspace_id": MOCK_WS_ID},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# -------------------------------------------------------------------------
# 2. Authenticated Grouping Tests
# -------------------------------------------------------------------------

def test_group_features_success(mock_auth_user, sample_feature_group_result):
    """Verify POST /api/v1/ai/features/group successfully returns GroupFeaturesResponse."""
    mock_service = MagicMock()
    mock_service.group_feature_requests = AsyncMock(
        return_value=GroupFeaturesResponse(
            workspace_id=MOCK_WS_ID,
            groups_created=1,
            total_feedback_analyzed=2,
            groups=[sample_feature_group_result],
            ungrouped_feedback_ids=[],
            execution_metadata={"latency_ms": 120.5, "provider": "groq", "model": "qwen/qwen3.8-27b"},
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    payload = {
        "workspace_id": MOCK_WS_ID,
        "feedback_ids": [MOCK_FEEDBACK_ID, "660011223344556677889905"],
        "force_regroup": False,
        "confidence_threshold": 0.6,
        "min_group_size": 1,
    }

    response = client.post("/api/v1/ai/features/group", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["workspace_id"] == MOCK_WS_ID
    assert data["groups_created"] == 1
    assert data["total_feedback_analyzed"] == 2
    assert len(data["groups"]) == 1
    assert data["groups"][0]["group_name"] == "Dark Mode Theme Support"
    assert data["groups"][0]["total_request_count"] == 2


def test_group_features_workspace_forbidden(mock_auth_user):
    """Verify POST /api/v1/ai/features/group propagates HTTP 403 Forbidden for unauthorized workspace."""
    mock_service = MagicMock()
    mock_service.group_feature_requests = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have active access to this workspace.",
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    response = client.post(
        "/api/v1/ai/features/group",
        json={"workspace_id": MOCK_WS_ID},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "access" in response.json()["detail"].lower()


def test_group_features_ai_rate_limit(mock_auth_user):
    """Verify POST /api/v1/ai/features/group converts AIRateLimitException to HTTP 429."""
    mock_service = MagicMock()
    mock_service.group_feature_requests = AsyncMock(
        side_effect=AIRateLimitException("Rate limit hit", provider="groq")
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    response = client.post(
        "/api/v1/ai/features/group",
        json={"workspace_id": MOCK_WS_ID},
    )
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# -------------------------------------------------------------------------
# 3. List & Get Feature Groups Tests
# -------------------------------------------------------------------------

def test_list_feature_groups_success(mock_auth_user, sample_feature_group_result):
    """Verify GET /api/v1/ai/features/groups returns list of feature groups."""
    mock_service = MagicMock()
    mock_service.get_feature_groups = AsyncMock(return_value=[sample_feature_group_result])

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    response = client.get(f"/api/v1/ai/features/groups?workspace_id={MOCK_WS_ID}&min_request_count=1")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["feature_group_id"] == MOCK_GROUP_ID
    assert data[0]["group_name"] == "Dark Mode Theme Support"


def test_get_feature_group_by_id_success(mock_auth_user, sample_feature_group_result):
    """Verify GET /api/v1/ai/features/groups/{id} returns feature group result."""
    mock_service = MagicMock()
    mock_service.get_feature_group_by_id = AsyncMock(return_value=sample_feature_group_result)

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    response = client.get(f"/api/v1/ai/features/groups/{MOCK_GROUP_ID}?workspace_id={MOCK_WS_ID}")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["feature_group_id"] == MOCK_GROUP_ID


def test_get_feature_group_by_id_not_found(mock_auth_user):
    """Verify GET /api/v1/ai/features/groups/{id} returns 404 for missing group."""
    mock_service = MagicMock()
    mock_service.get_feature_group_by_id = AsyncMock(
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature group not found")
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    response = client.get(f"/api/v1/ai/features/groups/{MOCK_GROUP_ID}?workspace_id={MOCK_WS_ID}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# -------------------------------------------------------------------------
# 4. Duplicate Detection Tests
# -------------------------------------------------------------------------

def test_detect_duplicates_success(mock_auth_user):
    """Verify POST /api/v1/ai/features/detect-duplicates returns DuplicateDetectionResponse."""
    mock_service = MagicMock()
    mock_service.detect_duplicates = AsyncMock(
        return_value=DuplicateDetectionResponse(
            workspace_id=MOCK_WS_ID,
            total_evaluated=2,
            duplicates_found=1,
            results=[
                DuplicateDetectionItem(
                    feedback_id=MOCK_FEEDBACK_ID,
                    matched_feedback_id="660011223344556677889905",
                    duplicate_type=DuplicateType.SEMANTIC_EQUIVALENT,
                    similarity_explanation="Both items request dark background styling.",
                    confidence=0.92,
                    recommendation="Merge into single Dark Mode feature group.",
                )
            ],
            execution_metadata={"duplicates_found": 1},
        )
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feature_intelligence_service] = lambda: mock_service

    payload = {
        "workspace_id": MOCK_WS_ID,
        "feedback_ids": [MOCK_FEEDBACK_ID, "660011223344556677889905"],
    }

    response = client.post("/api/v1/ai/features/detect-duplicates", json=payload)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["workspace_id"] == MOCK_WS_ID
    assert data["total_evaluated"] == 2
    assert data["duplicates_found"] == 1
    assert data["results"][0]["duplicate_type"] == "semantic_equivalent"

