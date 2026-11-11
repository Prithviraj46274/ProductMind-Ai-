"""
ProductMind AI — Prioritization Agent Unit Tests
Tests factor normalization, deterministic scoring engine, missing-data reweighting,
priority threshold mapping, ranking logic, and agent execution.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.ai.agents.prioritization import (
    PriorityLevel,
    FactorName,
    FactorWeightConfig,
    ThresholdConfig,
    ProductAnalyticsData,
    StrategicContext,
    PrioritizationAgentOutput,
    PrioritizationResult,
    PrioritizationAgent,
    compute_customer_demand_score,
    compute_urgency_score,
    compute_sentiment_score,
    compute_usage_impact_score,
    calculate_prioritization_score,
    rank_prioritization_results,
    format_prioritization_prompt_inputs,
)
from app.ai.agents.base import AgentExecutionMetadata, AgentExecutionResult
from app.ai.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    service = MagicMock(spec=LLMService)
    service.is_configured = True
    service.provider_name = "groq"
    service.model_name = "qwen/qwen3.8-27b"
    service.provider = MagicMock()
    return service


# =========================================================================
# 1. Config Validation Tests
# =========================================================================

def test_factor_weight_config_defaults():
    cfg = FactorWeightConfig()
    assert cfg.customer_demand == 0.25
    assert cfg.urgency == 0.20
    assert cfg.business_impact == 0.20
    assert cfg.strategic_alignment == 0.15
    assert cfg.sentiment == 0.10
    assert cfg.usage_impact == 0.10
    total = sum([
        cfg.customer_demand,
        cfg.urgency,
        cfg.business_impact,
        cfg.strategic_alignment,
        cfg.sentiment,
        cfg.usage_impact,
    ])
    assert abs(total - 1.0) < 0.001


def test_factor_weight_config_invalid_sum():
    with pytest.raises(ValidationError):
        FactorWeightConfig(
            customer_demand=0.5,
            urgency=0.5,
            business_impact=0.5,
            strategic_alignment=0.15,
            sentiment=0.10,
            usage_impact=0.10,
        )


def test_threshold_config_defaults_and_validation():
    cfg = ThresholdConfig()
    assert cfg.critical_min == 80.0
    assert cfg.high_min == 60.0
    assert cfg.medium_min == 40.0

    # Invalid hierarchy
    with pytest.raises(ValidationError):
        ThresholdConfig(critical_min=50.0, high_min=70.0, medium_min=40.0)


# =========================================================================
# 2. Factor Scoring Engine Tests
# =========================================================================

def test_compute_customer_demand_score():
    # 0 customers
    assert compute_customer_demand_score(0, 0) == 0.0

    # 1 customer, 1 request: 1 * 20 + 0 = 20
    assert compute_customer_demand_score(1, 1) == 20.0

    # 4 distinct customers, 4 requests: 4 * 20 + 0 = 80
    assert compute_customer_demand_score(4, 4) == 80.0

    # 4 distinct customers, 8 total requests (4 repeat): 80 + 4 * 5 = 100
    assert compute_customer_demand_score(8, 4) == 100.0

    # Capped at 100
    assert compute_customer_demand_score(50, 10) == 100.0


def test_compute_urgency_score():
    # Critical only: 100
    assert compute_urgency_score({"Critical": 5}) == 100.0

    # Low only: 25
    assert compute_urgency_score({"Low": 4}) == 25.0

    # Mixed: 1 Critical (100) + 1 Low (25) = 125 / 2 = 62.5
    assert compute_urgency_score({"Critical": 1, "Low": 1}) == 62.5

    # Empty fallback: 50.0
    assert compute_urgency_score({}) == 50.0


def test_compute_sentiment_score():
    # Negative friction: 90
    assert compute_sentiment_score({"Negative": 3}) == 90.0

    # Positive: 20
    assert compute_sentiment_score({"Positive": 2}) == 20.0

    # Mixed: 1 Negative (90) + 1 Positive (20) = 110 / 2 = 55.0
    assert compute_sentiment_score({"Negative": 1, "Positive": 1}) == 55.0


def test_compute_usage_impact_score():
    # Unavailable analytics
    assert compute_usage_impact_score(None) is None
    assert compute_usage_impact_score(ProductAnalyticsData(is_available=False)) is None

    # Available analytics
    analytics = ProductAnalyticsData(
        is_available=True,
        adoption_rate=70.0,
        user_engagement_score=80.0,
        active_users=500,  # 500 / 10 = 50.0
    )
    # (70 + 80 + 50) / 3 = 66.67
    score = compute_usage_impact_score(analytics)
    assert score is not None
    assert abs(score - 66.67) < 0.1


# =========================================================================
# 3. Deterministic Composite Scoring & Missing-Data Reweighting Tests
# =========================================================================

def test_calculate_prioritization_score_full_factors():
    # All factors available with equal scores of 80.0
    factor_scores = {
        FactorName.CUSTOMER_DEMAND.value: 80.0,
        FactorName.URGENCY.value: 80.0,
        FactorName.BUSINESS_IMPACT.value: 80.0,
        FactorName.STRATEGIC_ALIGNMENT.value: 80.0,
        FactorName.SENTIMENT.value: 80.0,
        FactorName.USAGE_IMPACT.value: 80.0,
    }

    result = calculate_prioritization_score(factor_scores)
    assert result["final_score"] == 80.0
    assert result["priority_level"] == PriorityLevel.CRITICAL
    assert result["coverage_percentage"] == 100.0
    assert len(result["missing_data"]) == 0


def test_calculate_prioritization_score_missing_usage_analytics():
    """
    Missing analytics reweighting policy test:
    When usage_impact is None, the remaining 5 factors (sum 0.90) are reweighted to 1.0.
    Coverage percentage must be recorded as 90.0%.
    """
    factor_scores = {
        FactorName.CUSTOMER_DEMAND.value: 100.0,      # weight 0.25 -> 0.25 / 0.90
        FactorName.URGENCY.value: 50.0,               # weight 0.20 -> 0.20 / 0.90
        FactorName.BUSINESS_IMPACT.value: 80.0,       # weight 0.20 -> 0.20 / 0.90
        FactorName.STRATEGIC_ALIGNMENT.value: 70.0,   # weight 0.15 -> 0.15 / 0.90
        FactorName.SENTIMENT.value: 60.0,             # weight 0.10 -> 0.10 / 0.90
        FactorName.USAGE_IMPACT.value: None,          # MISSING
    }

    result = calculate_prioritization_score(factor_scores)

    # Expected weighted score:
    # (100 * 0.25 + 50 * 0.20 + 80 * 0.20 + 70 * 0.15 + 60 * 0.10) / 0.90
    # = (25 + 10 + 16 + 10.5 + 6) / 0.90 = 67.5 / 0.90 = 75.0
    assert abs(result["final_score"] - 75.0) < 0.1
    assert result["priority_level"] == PriorityLevel.HIGH
    assert result["coverage_percentage"] == 90.0
    assert FactorName.USAGE_IMPACT.value in result["missing_data"]


def test_calculate_prioritization_score_threshold_classification():
    # Critical: >= 80.0
    res_crit = calculate_prioritization_score({FactorName.CUSTOMER_DEMAND.value: 85.0})
    assert res_crit["priority_level"] == PriorityLevel.CRITICAL

    # High: >= 60.0 and < 80.0
    res_high = calculate_prioritization_score({FactorName.CUSTOMER_DEMAND.value: 65.0})
    assert res_high["priority_level"] == PriorityLevel.HIGH

    # Medium: >= 40.0 and < 60.0
    res_med = calculate_prioritization_score({FactorName.CUSTOMER_DEMAND.value: 45.0})
    assert res_med["priority_level"] == PriorityLevel.MEDIUM

    # Low: < 40.0
    res_low = calculate_prioritization_score({FactorName.CUSTOMER_DEMAND.value: 30.0})
    assert res_low["priority_level"] == PriorityLevel.LOW


# =========================================================================
# 4. Ranking Logic Tests
# =========================================================================

def test_rank_prioritization_results():
    results = [
        PrioritizationResult(
            result_id="1",
            workspace_id="ws1",
            feature_group_id="fg1",
            group_name="Feature Low",
            final_score=35.0,
            priority_level=PriorityLevel.LOW,
            coverage_percentage=90.0,
            explanation="Low priority feature",
            recommendation="Backlog",
        ),
        PrioritizationResult(
            result_id="2",
            workspace_id="ws1",
            feature_group_id="fg2",
            group_name="Feature Critical",
            final_score=92.0,
            priority_level=PriorityLevel.CRITICAL,
            coverage_percentage=100.0,
            explanation="Critical priority feature",
            recommendation="Immediate sprint",
        ),
        PrioritizationResult(
            result_id="3",
            workspace_id="ws1",
            feature_group_id="fg3",
            group_name="Feature High",
            final_score=72.0,
            priority_level=PriorityLevel.HIGH,
            coverage_percentage=90.0,
            explanation="High priority feature",
            recommendation="Next milestone",
        ),
    ]

    # Standard descending sort
    ranked = rank_prioritization_results(results)
    assert [r.group_name for r in ranked] == ["Feature Critical", "Feature High", "Feature Low"]

    # Top-K limit
    ranked_top2 = rank_prioritization_results(results, top_k=2)
    assert len(ranked_top2) == 2
    assert ranked_top2[0].group_name == "Feature Critical"
    assert ranked_top2[1].group_name == "Feature High"

    # Minimum priority filter
    ranked_min_high = rank_prioritization_results(results, min_priority=PriorityLevel.HIGH)
    assert len(ranked_min_high) == 2
    assert all(r.priority_level in [PriorityLevel.CRITICAL, PriorityLevel.HIGH] for r in ranked_min_high)


# =========================================================================
# 5. Agent Prompt & Execution Tests
# =========================================================================

def test_format_prioritization_prompt_inputs():
    inputs = format_prioritization_prompt_inputs(
        group_id="fg101",
        title="Dark Mode Support",
        description="Theme customization for low-light environments",
        pain_points=["Eye strain late at night"],
        evidence=["It blinding at night", "Need night theme"],
        feedback_count=5,
        unique_customer_count=3,
        urgency_dist={"Medium": 3, "High": 2},
        sentiment_dist={"Negative": 4, "Neutral": 1},
        strategic_context=StrategicContext(
            company_stage="Growth",
            primary_business_goals=["Improve daily retention"],
        ),
        analytics_data=ProductAnalyticsData(
            is_available=True,
            active_users=1200,
            adoption_rate=65.0,
        ),
    )

    assert "Dark Mode Support" in inputs["feature_group_text"]
    assert "Eye strain late at night" in inputs["feature_group_text"]
    assert "Total Customer Requests: 5" in inputs["demand_metrics_text"]
    assert "Improve daily retention" in inputs["strategic_context_text"]
    assert "Active Users: 1200" in inputs["analytics_summary_text"]


@pytest.mark.asyncio
async def test_prioritization_agent_execution(mock_llm_service):
    agent = PrioritizationAgent(llm_service=mock_llm_service)

    fake_output = PrioritizationAgentOutput(
        feature_group_id="fg_test_1",
        business_impact_score=85.0,
        business_impact_explanation="Directly impacts daily user satisfaction and enterprise usability.",
        strategic_alignment_score=90.0,
        strategic_alignment_explanation="Aligns with corporate OKR to expand enterprise adoption.",
        customer_pain_point_severity="Severe friction during nighttime usage.",
        product_opportunity="Differentiates platform in high-intensity analyst workflows.",
        implementation_benefits=["Reduces visual fatigue", "Increases session duration"],
        delay_risks=["Customer churn to competitors offering dark theme"],
        supporting_evidence=["Working late at night is blinding"],
        reasoning="Strong business and strategic alignment warrants high priority.",
    )

    mock_llm_service.provider.ainvoke_structured = AsyncMock(return_value=fake_output)
    mock_llm_service.ainvoke_structured = mock_llm_service.provider.ainvoke_structured

    result = await agent.aevaluate(
        group_id="fg_test_1",
        title="Dark Mode Theme",
        description="Support dark appearance",
        pain_points=["Eye strain"],
        evidence=["Working late at night is blinding"],
        feedback_count=4,
        unique_customer_count=3,
        urgency_dist={"High": 2, "Medium": 2},
        sentiment_dist={"Negative": 3, "Neutral": 1},
    )

    assert result.data.feature_group_id == "fg_test_1"
    assert result.data.business_impact_score == 85.0
    assert result.data.strategic_alignment_score == 90.0
    assert len(result.data.implementation_benefits) == 2
    assert len(result.data.delay_risks) == 1
    mock_llm_service.ainvoke_structured.assert_called_once()


def test_prioritization_output_key_normalization():
    """
    Verifies that PrioritizationAgentOutput normalizes diverse LLM-generated key formats:
    - Title_Case_With_Underscores (e.g. Qwen style)
    - PascalCase
    - camelCase
    - Preserves canonical snake_case
    - Preserves unknown extra keys
    """
    # 1. Title_Case_With_Underscores (as produced by reasoning models)
    title_underscore_payload = {
        "Feature_Group_ID": "fg_qwen_1",
        "Business_Impact_Score": 75.0,
        "Business_Impact_Explanation": "Direct commercial value for retention.",
        "Strategic_Alignment_Score": 80.0,
        "Strategic_Alignment_Explanation": "Matches product roadmap for enterprise tier.",
        "Customer_Pain_Point_Severity": "High friction workflow blocker.",
        "Product_Opportunity": "Competitive parity in target vertical.",
        "Implementation_Benefits": ["Improved workflow speed", "Lower support costs"],
        "Delay_Risks": ["Risk of enterprise account attrition"],
        "Supporting_Evidence": ["Customer quotes from tickets"],
        "Reasoning": "Strong justification based on enterprise feedback.",
        "Extra_Metadata": "Preserved data",
    }
    model_obj = PrioritizationAgentOutput.model_validate(title_underscore_payload)
    assert model_obj.feature_group_id == "fg_qwen_1"
    assert model_obj.business_impact_score == 75.0
    assert model_obj.strategic_alignment_score == 80.0
    assert model_obj.customer_pain_point_severity == "High friction workflow blocker."
    assert len(model_obj.implementation_benefits) == 2

    # 2. PascalCase
    pascal_payload = {
        "FeatureGroupID": "fg_pascal_2",
        "BusinessImpactScore": 65.0,
        "BusinessImpactExplanation": "Moderate commercial utility across mid-market.",
        "StrategicAlignmentScore": 70.0,
        "StrategicAlignmentExplanation": "Supportive of standard core milestones.",
        "CustomerPainPointSeverity": "Moderate recurring annoyance.",
        "ImplementationBenefits": ["Automates manual export"],
        "DelayRisks": ["Slight delay in quarterly audits"],
        "Reasoning": "Sound operational improvement.",
    }
    obj_pascal = PrioritizationAgentOutput.model_validate(pascal_payload)
    assert obj_pascal.feature_group_id == "fg_pascal_2"
    assert obj_pascal.business_impact_score == 65.0
    assert obj_pascal.strategic_alignment_score == 70.0

    # 3. camelCase with 'id' shorthand
    camel_payload = {
        "id": "fg_camel_3",
        "businessImpactScore": 55.0,
        "businessImpactExplanation": "Minor efficiency gains for end users.",
        "strategicAlignmentScore": 60.0,
        "strategicAlignmentExplanation": "Acceptable alignment with secondary OKRs.",
        "customerPainPointSeverity": "Low severity UX friction.",
        "implementationBenefits": ["Better button visibility"],
        "delayRisks": ["Low risk"],
        "reasoning": "Standard minor enhancement.",
    }
    obj_camel = PrioritizationAgentOutput.model_validate(camel_payload)
    assert obj_camel.feature_group_id == "fg_camel_3"
    assert obj_camel.business_impact_score == 55.0

    # 4. Canonical keys take precedence over non-canonical keys
    conflict_payload = {
        "feature_group_id": "fg_canonical",
        "Feature_Group_ID": "fg_wrong",
        "business_impact_score": 90.0,
        "Business_Impact_Score": 10.0,
        "business_impact_explanation": "Canonical value must be preserved.",
        "strategic_alignment_score": 95.0,
        "strategic_alignment_explanation": "Canonical explanation preserved.",
        "customer_pain_point_severity": "Critical blocker.",
        "implementation_benefits": ["Key benefit"],
        "delay_risks": ["Immediate churn"],
        "reasoning": "High priority canonical record.",
    }
    obj_conflict = PrioritizationAgentOutput.model_validate(conflict_payload)
    assert obj_conflict.feature_group_id == "fg_canonical"
    assert obj_conflict.business_impact_score == 90.0


@pytest.mark.asyncio
async def test_prioritization_service_resolves_six_factors_from_rollups_and_evidence(mock_llm_service):
    """Verify PrioritizationService includes usage_impact (all 6 factors) from persisted analytics rollups or request evidence."""
    from bson import ObjectId
    from app.ai.agents.prioritization.schemas import AnalyzePrioritizationRequest
    from app.ai.agents.prioritization.service import PrioritizationService
    from app.core.enums import PlatformRole
    from app.models.analytics import AnalyticsDailyRollup, FeatureMetric, FunnelStepMetric

    ws_id = ObjectId()
    fg_id = ObjectId()
    fg_id_str = str(fg_id)

    mock_group = MagicMock()
    mock_group.id = fg_id
    mock_group.workspace_id = ws_id
    mock_group.title = "CSV Export Engine"
    mock_group.description = "Bulk CSV export for enterprise audits"
    mock_group.feedback_count = 4
    mock_group.unique_customer_count = 3
    mock_group.urgency_distribution = {"High": 3, "Medium": 1}
    mock_group.sentiment_distribution = MagicMock(positive=0, neutral=1, negative=3)
    mock_group.pain_points = ["Manual export takes hours"]
    mock_group.evidence = ["Need CSV export for quarterly audit"]
    mock_group.common_themes = ["CSV Export", "Reporting"]

    rollup = AnalyticsDailyRollup(
        workspaceId=ws_id,
        date="2026-11-11",
        activeUsers=250,
        totalSessions=400,
        totalEvents=1200,
        featureMetrics=[
            FeatureMetric(name="CSV Export Engine", eventCount=180, uniqueUsers=90, adoptionPercent=36.0)
        ],
        funnelMetrics=[
            FunnelStepMetric(step="Export Complete", users=90, conversionRate=60.0, dropOffRate=40.0)
        ],
    )

    mock_agent = MagicMock()
    mock_agent.agent_id = "prioritization_agent"
    mock_agent.aevaluate = AsyncMock(
        return_value=AgentExecutionResult(
            data=PrioritizationAgentOutput(
                feature_group_id=fg_id_str,
                business_impact_score=82.0,
                business_impact_explanation="Strong enterprise revenue retention driver.",
                strategic_alignment_score=85.0,
                strategic_alignment_explanation="Aligns with Q4 enterprise reporting OKR.",
                customer_pain_point_severity="High operational friction.",
                implementation_benefits=["Unblocks renewals"],
                delay_risks=["Churn risk"],
                supporting_evidence=["Need CSV export for quarterly audit"],
                reasoning="High demand and measurable usage impact.",
            ),
            metadata=AgentExecutionMetadata(
                agent_id="prioritization_agent",
                agent_name="Prioritization Agent",
                agent_version="1.0.0",
                provider="groq",
                model="qwen/qwen3.8-27b",
                latency_ms=100.0,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            ),
        )
    )

    fg_repo = MagicMock()
    fg_repo.find_by_workspace = AsyncMock(return_value=[mock_group])
    rollup_repo = MagicMock()
    rollup_repo.find_by_workspace = AsyncMock(return_value=[rollup])
    p_repo = MagicMock()
    p_repo.find_by_workspace_and_feature_group = AsyncMock(return_value=None)
    p_repo.create = AsyncMock(side_effect=lambda doc: setattr(doc, "id", ObjectId()) or doc)

    service = PrioritizationService(
        agent=mock_agent,
        prioritization_repo=p_repo,
        feature_group_repo=fg_repo,
        analytics_rollup_repo=rollup_repo,
    )
    user = MagicMock(id=ObjectId(), platform_role=PlatformRole.PLATFORM_ADMIN)

    res = await service.analyze_prioritization(
        request=AnalyzePrioritizationRequest(workspace_id=str(ws_id), force_reanalyze=True),
        user=user,
    )

    assert res.total_evaluated == 1
    item = res.results[0]
    expected_keys = {
        "customer_demand",
        "urgency",
        "business_impact",
        "strategic_alignment",
        "sentiment",
        "usage_impact",
    }
    assert set(item.factor_scores.keys()) == expected_keys
    assert item.coverage_percentage == 100.0
    assert item.missing_data == []
    # Verify deterministic composite score matches sum(score * weight)
    recomputed = round(sum(item.factor_scores[k] * item.factor_weights[k] for k in expected_keys), 2)
    assert abs(item.final_score - recomputed) <= 0.05

