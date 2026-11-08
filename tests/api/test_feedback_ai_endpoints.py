"""
ProductMind AI — Feedback Intelligence API Endpoints Integration Tests (Step 2)
Tests POST /api/v1/ai/feedback/{id}/analyze, GET /api/v1/ai/feedback/{id}/analysis,
and POST /api/v1/ai/feedback/analyze-batch with mocked service and auth layers.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.api.v1.endpoints.feedback_ai import get_feedback_intelligence_service
from app.ai.agents.feedback_intelligence import (
    FeedbackIntelligenceResult,
    FeedbackClassificationCategory,
    FeedbackSentimentType,
    FeedbackUrgency,
    ProductImpactArea,
    AnalysisStatus,
    FeedbackAnalysisResponse,
    BatchFeedbackItemResult,
    BatchFeedbackAnalysisResponse,
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
MOCK_WS_ID = ObjectId("660011223344556677889902")
MOCK_FEEDBACK_ID = "660011223344556677889903"


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
def sample_analysis_result():
    return FeedbackIntelligenceResult(
        feedback_id=MOCK_FEEDBACK_ID,
        category=FeedbackClassificationCategory.PERFORMANCE,
        secondary_tags=["dashboard", "latency"],
        sentiment=FeedbackSentimentType.NEGATIVE,
        sentiment_explanation="Customer states dashboard takes 30s to render.",
        urgency=FeedbackUrgency.HIGH,
        urgency_explanation="Severe latency blocks dashboard usage.",
        main_theme="Query Performance",
        subthemes=["rendering-speed"],
        customer_pain_point="Dashboard freeze during customer review",
        summary="Customer reports 30-second dashboard latency.",
        evidence=["dashboard takes 30s to render"],
        potential_product_impacts=[ProductImpactArea.PERFORMANCE, ProductImpactArea.USER_EXPERIENCE],
        suggested_action="Optimize aggregation queries for dashboard widgets.",
        confidence=0.92,
        analysis_status=AnalysisStatus.COMPLETED,
    )


def test_analyze_feedback_unauthenticated_returns_401():
    """Verify endpoint rejects unauthenticated requests with 401."""
    from app.api.dependencies import get_mongo_db
    app.dependency_overrides[get_mongo_db] = lambda: MagicMock()
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: AsyncMock()

    response = client.post(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analyze")
    assert response.status_code == 401


def test_analyze_feedback_success_mocked(mock_auth_user, sample_analysis_result):
    """Verify successful analysis execution returns 200 with structured intelligence."""
    mock_service = AsyncMock()
    mock_service.analyze_feedback_item.return_value = FeedbackAnalysisResponse(
        feedback_id=MOCK_FEEDBACK_ID,
        workspace_id=str(MOCK_WS_ID),
        title="Slow dashboard",
        analysis=sample_analysis_result,
        metadata={"provider": "groq", "model": "qwen/qwen3.8-27b", "latency_ms": 350.5},
        analyzed_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.post(
        f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analyze",
        json={"force_reanalyze": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["feedback_id"] == MOCK_FEEDBACK_ID
    assert data["analysis"]["category"] == "Performance"
    assert data["analysis"]["sentiment"] == "Negative"
    assert data["analysis"]["urgency"] == "High"
    assert data["analysis"]["confidence"] == 0.92
    assert "metadata" in data


def test_analyze_feedback_not_found(mock_auth_user):
    """Verify non-existent feedback returns HTTP 404."""
    mock_service = AsyncMock()
    mock_service.analyze_feedback_item.side_effect = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Feedback item '{MOCK_FEEDBACK_ID}' not found",
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.post(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analyze")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_analyze_feedback_unauthorized_workspace_returns_403(mock_auth_user):
    """Verify unauthorized workspace access returns HTTP 403 Forbidden."""
    mock_service = AsyncMock()
    mock_service.analyze_feedback_item.side_effect = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have active access to the workspace associated with this feedback item.",
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.post(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analyze")
    assert response.status_code == 403
    assert "workspace" in response.json()["detail"].lower()


def test_analyze_feedback_rate_limit_returns_429(mock_auth_user):
    """Verify provider rate-limit failure maps to HTTP 429."""
    mock_service = AsyncMock()
    mock_service.analyze_feedback_item.side_effect = AIRateLimitException(
        "Rate limit exceeded on TPM", provider="groq"
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.post(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analyze")
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_analyze_feedback_timeout_returns_504(mock_auth_user):
    """Verify provider timeout maps to HTTP 504 Gateway Timeout."""
    mock_service = AsyncMock()
    mock_service.analyze_feedback_item.side_effect = AITimeoutException(
        "Model timeout", provider="groq"
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.post(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analyze")
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_get_feedback_analysis_success(mock_auth_user, sample_analysis_result):
    """Verify GET /api/v1/ai/feedback/{id}/analysis retrieves stored analysis without invoking model."""
    mock_service = AsyncMock()
    mock_service.get_feedback_analysis.return_value = FeedbackAnalysisResponse(
        feedback_id=MOCK_FEEDBACK_ID,
        workspace_id=str(MOCK_WS_ID),
        title="Slow dashboard",
        analysis=sample_analysis_result,
        metadata={"provider": "groq", "cached": True},
        analyzed_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.get(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["feedback_id"] == MOCK_FEEDBACK_ID
    assert data["analysis"]["category"] == "Performance"
    assert data["metadata"]["cached"] is True


def test_get_feedback_analysis_not_yet_analyzed(mock_auth_user):
    """Verify GET returns 404 with guidance if item has not been analyzed yet."""
    mock_service = AsyncMock()
    mock_service.get_feedback_analysis.side_effect = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No AI analysis found for feedback item '{MOCK_FEEDBACK_ID}'. Execute POST /analyze first.",
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.get(f"/api/v1/ai/feedback/{MOCK_FEEDBACK_ID}/analysis")
    assert response.status_code == 404
    assert "execute post /analyze first" in response.json()["detail"].lower()


def test_analyze_feedback_batch_success(mock_auth_user, sample_analysis_result):
    """Verify POST /api/v1/ai/feedback/analyze-batch handles bounded batch of items."""
    mock_service = AsyncMock()
    mock_service.analyze_batch.return_value = BatchFeedbackAnalysisResponse(
        total_requested=2,
        successful=2,
        failed=0,
        results=[
            BatchFeedbackItemResult(
                feedback_id="660011223344556677889901",
                status="success",
                analysis=sample_analysis_result,
            ),
            BatchFeedbackItemResult(
                feedback_id="660011223344556677889902",
                status="success",
                analysis=sample_analysis_result,
            ),
        ],
    )

    app.dependency_overrides[get_current_user] = lambda: mock_auth_user
    app.dependency_overrides[get_feedback_intelligence_service] = lambda: mock_service

    response = client.post(
        "/api/v1/ai/feedback/analyze-batch",
        json={"feedback_ids": ["660011223344556677889901", "660011223344556677889902"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_requested"] == 2
    assert data["successful"] == 2
    assert data["failed"] == 0
    assert len(data["results"]) == 2
