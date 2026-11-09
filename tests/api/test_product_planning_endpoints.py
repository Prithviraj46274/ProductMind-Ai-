"""
ProductMind AI — Product Planning API Endpoints Integration Tests
Tests POST /generate, POST /generate-prd, POST /generate-user-stories,
GET /{id}, GET /, and PATCH /{id}/review.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user, get_mongo_db
from app.api.v1.endpoints.planning_ai import get_product_planning_service
from app.ai.agents.product_planning import (
    GenerateProductPlanRequest,
    GeneratePRDRequest,
    GenerateUserStoriesRequest,
    ReviewPlanRequest,
    ProductPlanResponse,
    ProductRequirementsDocument,
    UserStory,
    AcceptanceCriterion,
    TechnicalRequirement,
    SuccessMetric,
    RiskItem,
    RoadmapPhase,
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
MOCK_PLAN_ID = "660011223344556677889903"
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
def sample_plan_response():
    return ProductPlanResponse(
        planning_id=MOCK_PLAN_ID,
        workspace_id=MOCK_WS_ID,
        feature_group_id=MOCK_GROUP_ID,
        prioritization_result_id=None,
        title="Automated CSV Export Engine",
        version="1.0.0",
        status="Pending Review",
        prd=ProductRequirementsDocument(
            title="Automated CSV Export Engine",
            executive_summary="Empowers analysts to export dashboard data in standard CSV format.",
            problem_statement="Analysts spend 2 hours daily manually copying tables into Excel.",
            background="Top customer renewal blocker.",
            proposed_solution="Async streaming CSV download button.",
        ),
        user_stories=[
            UserStory(
                story_id="US-001",
                title="Download CSV",
                description="As an analyst, I want to download CSV data, so that I can audit financials.",
                persona="Financial Analyst",
                business_value="Saves 2 hours daily",
                priority="Critical",
                acceptance_criteria=[
                    AcceptanceCriterion(
                        criterion_id="AC-001",
                        description="Given table, When user clicks Export, Then CSV downloads",
                        testable=True,
                    )
                ],
            )
        ],
        technical_requirements=[
            TechnicalRequirement(
                title="Async Streaming Endpoint",
                description="Stream CSV response.",
                category="api",
                rationale="Prevents OOM.",
                confidence=0.9,
                requires_engineering_review=True,
            )
        ],
        success_metrics=[
            SuccessMetric(
                metric_name="Weekly Export Users",
                description="Unique users triggering export",
                measurement_method="Analytics log count",
                baseline=None,
                suggested_target="500 users",
                requires_confirmation=True,
            )
        ],
        risk_analysis=[
            RiskItem(
                description="Heavy memory usage",
                category="technical",
                impact="High",
                likelihood="Medium",
                mitigation="Worker queues",
                requires_human_review=True,
            )
        ],
        roadmap_recommendations=[
            RoadmapPhase(
                phase_name="Phase 1 – Core Export",
                objective="Deliver basic CSV streaming",
                tasks=["Build API endpoint"],
                deliverables=["Export endpoint v1"],
                suggested_sequencing=1,
            )
        ],
        supporting_evidence=["We need CSV export to renew our contract."],
        review_notes=None,
        reviewed_by=None,
        reviewed_at=None,
    )


# ---------------------------------------------------------------------------
# Unauthenticated Tests (must return 401)
# ---------------------------------------------------------------------------

def test_generate_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    resp = client.post(
        "/api/v1/ai/planning/generate",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_generate_prd_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    resp = client.post(
        "/api/v1/ai/planning/generate-prd",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_generate_user_stories_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    resp = client.post(
        "/api/v1/ai/planning/generate-user-stories",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_plan_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    resp = client.get(f"/api/v1/ai/planning/{MOCK_PLAN_ID}")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_plans_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    resp = client.get(f"/api/v1/ai/planning/?workspace_id={MOCK_WS_ID}")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_review_plan_unauthenticated():
    mock_db = MagicMock()
    app.dependency_overrides[get_mongo_db] = lambda: mock_db
    resp = client.patch(
        f"/api/v1/ai/planning/{MOCK_PLAN_ID}/review",
        json={"review_status": "approved"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Authenticated Happy Paths
# ---------------------------------------------------------------------------

def test_generate_plan_success(mock_auth_user, sample_plan_response):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_plan = AsyncMock(return_value=sample_plan_response)
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    payload = {
        "workspace_id": MOCK_WS_ID,
        "feature_group_id": MOCK_GROUP_ID,
    }
    resp = client.post("/api/v1/ai/planning/generate", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["planning_id"] == MOCK_PLAN_ID
    assert data["title"] == "Automated CSV Export Engine"
    assert data["status"] == "Pending Review"
    assert len(data["user_stories"]) == 1
    assert data["user_stories"][0]["story_id"] == "US-001"
    assert len(data["technical_requirements"]) == 1
    assert data["technical_requirements"][0]["requires_engineering_review"] is True


def test_generate_prd_only_success(mock_auth_user, sample_plan_response):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_prd_only = AsyncMock(return_value=sample_plan_response)
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    payload = {
        "workspace_id": MOCK_WS_ID,
        "feature_group_id": MOCK_GROUP_ID,
    }
    resp = client.post("/api/v1/ai/planning/generate-prd", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["planning_id"] == MOCK_PLAN_ID
    assert data["prd"]["title"] == "Automated CSV Export Engine"


def test_generate_user_stories_only_success(mock_auth_user, sample_plan_response):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_user_stories_only = AsyncMock(return_value=sample_plan_response)
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    payload = {
        "workspace_id": MOCK_WS_ID,
        "feature_group_id": MOCK_GROUP_ID,
    }
    resp = client.post("/api/v1/ai/planning/generate-user-stories", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["user_stories"]) == 1


def test_get_plan_by_id_success(mock_auth_user, sample_plan_response):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.get_plan_by_id = AsyncMock(return_value=sample_plan_response)
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.get(f"/api/v1/ai/planning/{MOCK_PLAN_ID}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["planning_id"] == MOCK_PLAN_ID


def test_list_plans_success(mock_auth_user, sample_plan_response):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.list_plans = AsyncMock(return_value=[sample_plan_response])
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.get(f"/api/v1/ai/planning/?workspace_id={MOCK_WS_ID}&limit=10&skip=0")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["planning_id"] == MOCK_PLAN_ID


def test_update_review_status_success(mock_auth_user, sample_plan_response):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    approved_plan = sample_plan_response.model_copy()
    approved_plan.status = "Approved"
    approved_plan.reviewed_by = str(mock_auth_user.id)

    mock_service = MagicMock()
    mock_service.update_review_status = AsyncMock(return_value=approved_plan)
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.patch(
        f"/api/v1/ai/planning/{MOCK_PLAN_ID}/review",
        json={"review_status": "approved", "review_notes": "Meets Q4 requirements."},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] == "Approved"


# ---------------------------------------------------------------------------
# Business Errors & AI Exception Mappings
# ---------------------------------------------------------------------------

def test_generate_plan_workspace_forbidden(mock_auth_user):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_plan = AsyncMock(
        side_effect=HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    )
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.post(
        "/api/v1/ai/planning/generate",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_generate_plan_rate_limit_error(mock_auth_user):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_plan = AsyncMock(
        side_effect=AIRateLimitException("Groq rate limit", provider="groq")
    )
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.post(
        "/api/v1/ai/planning/generate",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_generate_plan_timeout_error(mock_auth_user):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_plan = AsyncMock(
        side_effect=AITimeoutException("Groq timed out", provider="groq")
    )
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.post(
        "/api/v1/ai/planning/generate",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT


def test_generate_plan_provider_error(mock_auth_user):
    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    mock_service = MagicMock()
    mock_service.generate_plan = AsyncMock(
        side_effect=AIProviderException("Groq 500 internal error", provider="groq")
    )
    app.dependency_overrides[get_product_planning_service] = lambda: mock_service

    resp = client.post(
        "/api/v1/ai/planning/generate",
        json={"workspace_id": MOCK_WS_ID, "feature_group_id": MOCK_GROUP_ID},
    )
    assert resp.status_code == status.HTTP_502_BAD_GATEWAY

