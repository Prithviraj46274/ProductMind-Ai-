"""
ProductMind AI — Feedback Intelligence Agent Unit Tests (Step 2)
Tests schema constraints, category classification, sentiment analysis,
calibrated urgency, grounded evidence validation, and ambiguity handling.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.ai.agents.feedback_intelligence import (
    FeedbackIntelligenceAgent,
    FeedbackIntelligenceResult,
    FeedbackClassificationCategory,
    FeedbackSentimentType,
    FeedbackUrgency,
    ProductImpactArea,
    AnalysisStatus,
)
from app.ai.agents.base import AgentExecutionResult
from app.ai.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    service = MagicMock(spec=LLMService)
    service.is_configured = True
    service.provider_name = "groq"
    service.model_name = "qwen/qwen3.8-27b"
    service.provider = MagicMock()
    return service


@pytest.fixture
def sample_valid_analysis():
    return FeedbackIntelligenceResult(
        feedback_id="6611223344556677889900aa",
        category=FeedbackClassificationCategory.PERFORMANCE,
        secondary_tags=["dashboard", "latency", "large-datasets"],
        sentiment=FeedbackSentimentType.NEGATIVE,
        sentiment_explanation="Customer states dashboard takes over 30 seconds to load.",
        urgency=FeedbackUrgency.HIGH,
        urgency_explanation="Severe latency blocks daily workflow for enterprise tier customer.",
        main_theme="Dashboard Query Performance",
        subthemes=["loading-times", "query-optimization"],
        customer_pain_point="Dashboard freezes when switching between filtered views with >5k items.",
        summary="Customer reports unacceptable 30s dashboard latency when viewing large datasets.",
        evidence=["dashboard takes over 30 seconds to load", "freezes when switching between filtered views"],
        potential_product_impacts=[
            ProductImpactArea.PERFORMANCE,
            ProductImpactArea.USER_EXPERIENCE,
            ProductImpactArea.CUSTOMER_RETENTION,
        ],
        suggested_action="Optimize aggregation pipelines and add indexing to dashboard metrics endpoint.",
        confidence=0.95,
        analysis_status=AnalysisStatus.COMPLETED,
    )


def test_feedback_result_schema_validation(sample_valid_analysis):
    """Verify schema correctly serializes and deserializes conforming intelligence data."""
    data = sample_valid_analysis.model_dump()
    reconstructed = FeedbackIntelligenceResult(**data)
    assert reconstructed.feedback_id == "6611223344556677889900aa"
    assert reconstructed.category == FeedbackClassificationCategory.PERFORMANCE
    assert reconstructed.sentiment == FeedbackSentimentType.NEGATIVE
    assert reconstructed.urgency == FeedbackUrgency.HIGH
    assert reconstructed.confidence == 0.95
    assert len(reconstructed.evidence) == 2


def test_feedback_result_rejects_out_of_bounds_confidence():
    """Verify confidence must be strictly between 0.0 and 1.0."""
    with pytest.raises(ValidationError):
        FeedbackIntelligenceResult(
            feedback_id="123",
            category=FeedbackClassificationCategory.BUG,
            sentiment=FeedbackSentimentType.NEGATIVE,
            sentiment_explanation="Negative tone",
            urgency=FeedbackUrgency.MEDIUM,
            urgency_explanation="Medium urgency",
            main_theme="Bugs",
            customer_pain_point="Error occurred",
            summary="Error summary",
            evidence=["error"],
            suggested_action="Fix error",
            confidence=1.5,  # Invalid: > 1.0
        )


def test_feedback_result_insufficient_info_restrains_confidence():
    """Verify insufficient information status enforces restrained confidence score."""
    result = FeedbackIntelligenceResult(
        feedback_id="123",
        category=FeedbackClassificationCategory.OTHER,
        sentiment=FeedbackSentimentType.NEUTRAL,
        sentiment_explanation="No clear sentiment",
        urgency=FeedbackUrgency.LOW,
        urgency_explanation="Lacks actionable severity",
        main_theme="Vague Feedback",
        customer_pain_point="Unclear statement",
        summary="Customer said 'not good' without additional context.",
        evidence=[],
        suggested_action="Request clarification from customer",
        confidence=0.9,  # High confidence on insufficient info should be auto-restrained
        analysis_status=AnalysisStatus.INSUFFICIENT_INFORMATION,
    )
    assert result.confidence <= 0.5


def test_feedback_agent_input_validation():
    """Verify input validation enforces feedback_id and content existence."""
    agent = FeedbackIntelligenceAgent()

    # Missing feedback_id
    with pytest.raises(ValueError) as exc_info:
        agent.validate_input({"title": "Test Title", "description": "Desc"})
    assert "feedback_id is required" in str(exc_info.value)

    # Missing both title and description
    with pytest.raises(ValueError) as exc_info:
        agent.validate_input({"feedback_id": "123", "title": "", "description": ""})
    assert "must contain a non-empty title or description" in str(exc_info.value)

    # Valid input with customer context normalization
    validated = agent.validate_input({
        "feedback_id": "12345",
        "title": "Slow Search",
        "description": "Search takes 10s",
        "customer_name": "Alice Corp",
        "company_name": "Acme",
    })
    assert validated["feedback_id"] == "12345"
    assert "Alice Corp" in validated["customer_context"]
    assert "Acme" in validated["customer_context"]


@pytest.mark.asyncio
async def test_feedback_agent_execution_success(mock_llm_service, sample_valid_analysis):
    """Verify full agent execution produces typed result with execution metadata."""
    mock_llm_service.provider.ainvoke_structured = AsyncMock(return_value=sample_valid_analysis)

    agent = FeedbackIntelligenceAgent(llm_service=mock_llm_service)
    result = await agent.execute({
        "feedback_id": "6611223344556677889900aa",
        "title": "Slow dashboard loading",
        "description": "Dashboard takes over 30 seconds to load and freezes when switching filtered views.",
        "customer_name": "Enterprise Client",
    })

    assert isinstance(result, AgentExecutionResult)
    assert result.data.feedback_id == "6611223344556677889900aa"
    assert result.data.category == FeedbackClassificationCategory.PERFORMANCE
    assert result.data.sentiment == FeedbackSentimentType.NEGATIVE
    assert result.data.urgency == FeedbackUrgency.HIGH
    assert result.metadata.agent_id == "feedback_intelligence_agent"
    assert result.metadata.latency_ms >= 0
    assert mock_llm_service.provider.ainvoke_structured.await_count == 1

