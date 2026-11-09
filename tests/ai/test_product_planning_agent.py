"""
ProductMind AI — Product Planning Agent Unit Tests
Tests schemas, prompt formatting, validation rules, zero-fabrication policies,
evidence grounding, and agent execution with mocked LLM responses.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.ai.agents.product_planning.agent import (
    ProductPlanningAgent,
    format_product_planning_prompt_inputs,
)
from app.ai.agents.product_planning.schemas import (
    AcceptanceCriterion,
    GenerateProductPlanRequest,
    ProductPlanningAgentOutput,
    ProductRequirementsDocument,
    ProductRequirement,
    RequirementOrigin,
    ProductStrategicContext,
    ReviewPlanRequest,
    RiskItem,
    RoadmapPhase,
    SuccessMetric,
    TechnicalRequirement,
    UserStory,
    infer_expected_direction,
)
from app.ai.agents.product_planning.service import ProductPlanningService
from app.ai.agents.base import AgentExecutionMetadata, AgentExecutionResult


# ---------------------------------------------------------------------------
# Schema & Policy Tests
# ---------------------------------------------------------------------------

def test_success_metric_zero_fabrication_policy():
    """Verify SuccessMetric requires baseline to be None if unknown and marks confirmation needed."""
    metric = SuccessMetric(
        metric_name="Adoption Rate",
        description="Percentage of active users who trigger CSV export weekly",
        measurement_method="Daily analytics events count",
        expected_direction="increase",
        baseline=None,  # Zero-fabrication: must be None when not measured yet
        suggested_target="25%",
        requires_confirmation=True,
    )
    assert metric.baseline is None
    assert metric.requires_confirmation is True
    assert metric.expected_direction == "increase"


def test_user_story_and_acceptance_criteria_format():
    """Verify UserStory and AcceptanceCriterion Given-When-Then specification."""
    ac = AcceptanceCriterion(
        criterion_id="AC-001",
        description="Given a user on reports page, When they click 'Export CSV', Then a file download initiates within 2s",
        scenario_type="positive",
        testable=True,
        related_story_id="US-001",
    )
    story = UserStory(
        story_id="US-001",
        title="Export CSV Reports",
        description="As a financial analyst, I want to export dashboard data to CSV, so that I can perform custom quarterly audits.",
        persona="Financial Analyst",
        business_value="Saves 3 hours/week of manual spreadsheet entry",
        priority="High",
        related_requirements=["REQ-001", "REQ-002"],
        acceptance_criteria=[ac],
        dependencies=[],
        supporting_feedback_ids=["fb_001", "fb_002"],
    )
    assert story.story_id == "US-001"
    assert len(story.acceptance_criteria) == 1
    assert story.acceptance_criteria[0].testable is True
    assert "Given" in story.acceptance_criteria[0].description


def test_technical_requirement_engineering_review_flag():
    """Verify technical suggestions are explicitly flagged for human engineering review."""
    tech = TechnicalRequirement(
        title="Streaming CSV Generation Endpoint",
        description="Use async generator streaming to avoid buffering 50MB files in memory.",
        category="api",
        rationale="Prevents OOM errors during concurrent peak export requests.",
        confidence=0.9,
        requires_engineering_review=True,
    )
    assert tech.category == "api"
    assert tech.requires_engineering_review is True
    assert tech.confidence == 0.9


def test_risk_item_categorization():
    """Verify RiskItem requires human review and clear mitigation."""
    risk = RiskItem(
        description="Database timeout on large dataset exports exceeding 100k rows.",
        category="technical",
        impact="High",
        likelihood="Medium",
        mitigation="Enforce asynchronous background job with presigned S3 download link.",
        requires_human_review=True,
    )
    assert risk.category == "technical"
    assert risk.impact == "High"
    assert risk.requires_human_review is True


def test_roadmap_phase_sequencing():
    """Verify RoadmapPhase contains sequencing and concrete tasks."""
    phase = RoadmapPhase(
        phase_name="Phase 1 – Core Ingestion & Engine",
        objective="Deploy backend export streaming pipeline",
        tasks=["Design CSV export schema", "Implement async streaming route"],
        dependencies=[],
        deliverables=["Export API v1", "Unit test suite"],
        suggested_sequencing=1,
        risks=["Memory exhaustion on large tables"],
    )
    assert phase.suggested_sequencing == 1
    assert len(phase.tasks) == 2


# ---------------------------------------------------------------------------
# Prompt Formatting Tests
# ---------------------------------------------------------------------------

def test_format_product_planning_prompt_inputs():
    """Verify format_product_planning_prompt_inputs structures domain inputs properly."""
    strategic_ctx = ProductStrategicContext(
        product_name="ProductMind AI",
        product_description="AI copilot for product management",
        business_goals=["Reduce user churn by 15%"],
        current_quarter_objectives=["Ship CSV reporting"],
        technical_constraints=["MongoDB 7.0+", "FastAPI backend"],
        known_dependencies=["Auth0", "AWS S3"],
        additional_planning_instructions="Ensure enterprise SOC2 audit compliance.",
    )

    prioritization_data = {
        "final_score": 84.5,
        "priority_level": "Critical",
        "factor_scores": {
            "customer_demand": 85.0,
            "urgency": 80.0,
            "business_impact": 90.0,
            "strategic_alignment": 85.0,
        },
        "explanation": "Critical enterprise demand with direct churn risk.",
        "implementation_benefits": ["Eliminates manual reporting overhead"],
        "delay_risks": ["Key enterprise renewals at risk"],
        "missing_data": ["usage_impact"],
    }

    formatted = format_product_planning_prompt_inputs(
        group_id="fg_12345",
        title="CSV Export Capabilities",
        description="Users need automated CSV export for quarterly reporting.",
        feedback_count=35,
        unique_customer_count=18,
        pain_points=["Manual copy-paste takes 2 hours", "No audit trails"],
        evidence=["We need CSV export to renew our contract.", "Export button is missing."],
        themes=["Reporting", "Enterprise Automation"],
        urgency_dist={"critical": 5, "high": 12, "medium": 15, "low": 3},
        sentiment_dist={"negative": 18, "neutral": 12, "positive": 5},
        prioritization_data=prioritization_data,
        strategic_context=strategic_ctx,
    )

    assert "fg_12345" in formatted["feature_group_text"]
    assert "35 requests from 18 distinct accounts" in formatted["feature_group_text"]
    assert "Manual copy-paste takes 2 hours" in formatted["feature_group_text"]
    assert "We need CSV export to renew our contract." in formatted["feature_group_text"]

    assert "84.5 / 100 (Critical Priority)" in formatted["prioritization_text"]
    assert "Eliminates manual reporting overhead" in formatted["prioritization_text"]
    assert "usage_impact" in formatted["prioritization_text"]

    assert "Product: ProductMind AI" in formatted["strategic_context_text"]
    assert "Reduce user churn by 15%" in formatted["strategic_context_text"]
    assert "FastAPI backend" in formatted["strategic_context_text"]
    assert "Ensure enterprise SOC2 audit compliance" in formatted["strategic_context_text"]


def test_format_product_planning_prompt_missing_prioritization():
    """Verify prompt formatting gracefully handles missing prioritization scenario."""
    formatted = format_product_planning_prompt_inputs(
        group_id="fg_999",
        title="Dark Mode",
        description="Users request dark mode theme",
        feedback_count=5,
        unique_customer_count=4,
        pain_points=["Eye strain at night"],
        evidence=["Please add dark mode"],
        themes=["UI/UX"],
        prioritization_data=None,
        strategic_context=None,
    )
    assert "Prioritization Status: Not separately evaluated before planning" in formatted["prioritization_text"]
    assert "standard b2b saas product best practices" in formatted["strategic_context_text"].lower()


# ---------------------------------------------------------------------------
# Agent Input Validation Tests
# ---------------------------------------------------------------------------

def test_agent_validate_input_empty_feature_group():
    """Verify validation raises ValueError on empty feature group text."""
    agent = ProductPlanningAgent(llm_service=MagicMock())
    with pytest.raises(ValueError, match="feature_group_text cannot be empty"):
        agent.validate_input({"feature_group_text": ""})


def test_agent_validate_input_defaults():
    """Verify agent fills default text for optional prompt variables."""
    agent = ProductPlanningAgent(llm_service=MagicMock())
    validated = agent.validate_input({"feature_group_text": "Feature: CSV Export"})
    assert validated["feature_group_text"] == "Feature: CSV Export"
    assert "Prioritization Status" in validated["prioritization_text"]
    assert "Standard SaaS" in validated["strategic_context_text"]


# ---------------------------------------------------------------------------
# Agent Execution with Mocked LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_agenerate_plan_execution():
    """Verify full agent execution pipeline with mocked LLM provider."""
    mock_llm_service = MagicMock()
    mock_llm_service.is_configured = True
    mock_llm_service.provider_name = "groq"
    mock_llm_service.model_name = "qwen/qwen3.8-27b"

    fake_prd = ProductRequirementsDocument(
        title="Automated CSV Export Engine",
        executive_summary="Empowers analysts to export dashboard data in standard CSV format.",
        problem_statement="Analysts spend 2 hours daily manually copying tables into Excel.",
        background="Customer feedback identified CSV export as a top blocker for renewals.",
        customer_pain_points=["Manual data re-entry", "Lack of audit trails"],
        target_users=["Financial Analysts", "Operations Leads"],
        business_objectives=["Improve retention", "Unblock 3 enterprise renewals"],
        proposed_solution="A secure async streaming CSV download button on dashboard tables.",
        functional_requirements=["Stream CSV up to 100k rows", "Include timestamp headers"],
        non_functional_requirements=["Download begins within 3 seconds", "SOC2 compliance"],
        workflows=["1. User clicks Export -> 2. Selects fields -> 3. File downloads"],
        dependencies=["Reporting Service", "AWS S3"],
        risks_and_assumptions=["Assumes user has read permissions on dataset"],
        success_metrics=["CSV Export Adoption Rate > 20% in 60 days"],
        out_of_scope=["PDF export", "Scheduled FTP push"],
        open_questions=["What is the max row limit for free tier?"],
        supporting_evidence=["We need CSV export to renew our contract."],
    )

    fake_output = ProductPlanningAgentOutput(
        feature_group_id="fg_test_100",
        prd=fake_prd,
        user_stories=[
            UserStory(
                story_id="US-001",
                title="Download CSV from Table View",
                description="As an analyst, I want to download CSV from table view, so that I can analyze in Excel.",
                persona="Financial Analyst",
                business_value="Saves 2 hours daily",
                priority="Critical",
                related_requirements=["REQ-001"],
                acceptance_criteria=[
                    AcceptanceCriterion(
                        criterion_id="AC-001",
                        description="Given table with data, When user clicks Export, Then CSV downloads",
                        scenario_type="positive",
                        testable=True,
                    )
                ],
            )
        ],
        technical_requirements=[
            TechnicalRequirement(
                title="Async Streaming Endpoint",
                description="Stream CSV response directly to HTTP client.",
                category="api",
                rationale="Prevents memory spikes.",
                confidence=0.9,
                requires_engineering_review=True,
            )
        ],
        success_metrics=[
            SuccessMetric(
                metric_name="Weekly Export Users",
                description="Unique users triggering export",
                measurement_method="Analytics log count",
                expected_direction="increase",
                baseline=None,
                suggested_target="500 users",
                requires_confirmation=True,
            )
        ],
        risk_analysis=[
            RiskItem(
                description="Heavy memory usage during peak hours",
                category="technical",
                impact="High",
                likelihood="Medium",
                mitigation="Worker queues with rate limiting",
                requires_human_review=True,
            )
        ],
        roadmap_recommendations=[
            RoadmapPhase(
                phase_name="Phase 1 – Core Export",
                objective="Deliver basic CSV streaming",
                tasks=["Build API endpoint", "Add UI export button"],
                dependencies=[],
                deliverables=["Export endpoint v1"],
                suggested_sequencing=1,
            )
        ],
        supporting_evidence=["We need CSV export to renew our contract."],
    )

    mock_llm_service.provider.ainvoke_structured = AsyncMock(return_value=fake_output)
    mock_llm_service.ainvoke_structured = mock_llm_service.provider.ainvoke_structured

    agent = ProductPlanningAgent(llm_service=mock_llm_service)

    result = await agent.agenerate_plan(
        group_id="fg_test_100",
        title="CSV Export",
        description="Export dashboard data",
        feedback_count=20,
        unique_customer_count=10,
        pain_points=["Manual entry takes hours"],
        evidence=["We need CSV export to renew our contract."],
        themes=["Reporting"],
    )

    assert result is not None
    assert isinstance(result, AgentExecutionResult)
    assert result.data.feature_group_id == "fg_test_100"
    assert result.data.prd.title == "Automated CSV Export Engine"
    assert len(result.data.user_stories) == 1
    assert result.data.user_stories[0].story_id == "US-001"
    assert len(result.data.technical_requirements) == 1
    assert result.data.technical_requirements[0].requires_engineering_review is True
    assert result.data.success_metrics[0].baseline is None
    assert result.data.risk_analysis[0].requires_human_review is True
    assert result.metadata.agent_id == "product_planning_agent"
    assert result.metadata.provider == "groq"


# ---------------------------------------------------------------------------
# Evidence Grounding & Origin Classification Tests
# ---------------------------------------------------------------------------

def test_requirement_origin_classification():
    """Verify ProductRequirement properly classifies origin across all 4 types."""
    req_source = ProductRequirement(
        requirement_id="REQ-001",
        title="Direct Table Export Button",
        description="Provide export button on transaction table",
        origin=RequirementOrigin.SOURCE_SUPPORTED,
        is_confirmed=True,
        requires_confirmation=False,
        source_reference="Please add an export button directly on the transaction and retention tables.",
    )
    assert req_source.origin == RequirementOrigin.SOURCE_SUPPORTED
    assert req_source.is_confirmed is True
    assert req_source.requires_confirmation is False
    assert req_source.source_reference is not None

    req_user = ProductRequirement(
        requirement_id="REQ-002",
        title="Role-Based Access Control",
        description="Enforce RBAC per workspace for export actions",
        origin=RequirementOrigin.USER_PROVIDED,
        is_confirmed=True,
        requires_confirmation=False,
        source_reference="Enforce strict role-based access control and rate-limiting per workspace.",
    )
    assert req_user.origin == RequirementOrigin.USER_PROVIDED
    assert req_user.is_confirmed is True

    req_ai = ProductRequirement(
        requirement_id="NFR-001",
        title="Latency Threshold Suggestion",
        description="Target execution latency to be confirmed by engineering review",
        origin=RequirementOrigin.AI_RECOMMENDATION,
        is_confirmed=False,
        requires_confirmation=True,
        numerical_threshold=None,
    )
    assert req_ai.origin == RequirementOrigin.AI_RECOMMENDATION
    assert req_ai.is_confirmed is False
    assert req_ai.requires_confirmation is True


def test_unsupported_numerical_threshold_policy():
    """Verify that ungrounded numerical thresholds must be null and unconfirmed."""
    req = ProductRequirement(
        requirement_id="NFR-002",
        title="Service Availability Target",
        description="SLA target to be established based on infrastructure tier",
        origin=RequirementOrigin.AI_RECOMMENDATION,
        is_confirmed=False,
        requires_confirmation=True,
        numerical_threshold=None,  # Zero-fabrication: ungrounded numerical targets are None
    )
    assert req.numerical_threshold is None
    assert req.is_confirmed is False
    assert req.requires_confirmation is True


def test_user_provided_technical_constraints_preservation():
    """Verify that user-provided technical constraints are marked user_provided and confirmed."""
    tech = TechnicalRequirement(
        title="AWS S3 File Storage",
        description="Exported files must be staged in AWS S3 buckets.",
        category="architecture",
        rationale="Mandated by organizational strategic context.",
        confidence=1.0,
        requires_engineering_review=False,
        origin=RequirementOrigin.USER_PROVIDED,
        is_confirmed=True,
        source_reference="User technical constraint: AWS S3 for file storage",
    )
    assert tech.origin == RequirementOrigin.USER_PROVIDED
    assert tech.is_confirmed is True
    assert tech.requires_engineering_review is False
    assert "AWS S3" in tech.source_reference


def test_source_supported_requirements_evidence_references():
    """Verify source-supported requirements retain traceable evidence references."""
    quote = "Our compliance audit requires weekly CSV exports. Without this, our renewal is blocked."
    req = ProductRequirement(
        requirement_id="REQ-003",
        title="Weekly Compliance CSV Export",
        description="Allow compliance team to export weekly CSV data",
        origin=RequirementOrigin.SOURCE_SUPPORTED,
        is_confirmed=True,
        requires_confirmation=False,
        source_reference=quote,
    )
    assert req.source_reference == quote
    assert req.origin == RequirementOrigin.SOURCE_SUPPORTED
    assert req.is_confirmed is True


def test_ai_recommendations_distinguishable_from_confirmed():
    """Verify AI recommendations remain clearly distinguishable from confirmed requirements."""
    confirmed_req = ProductRequirement(
        requirement_id="REQ-001",
        title="CSV Download",
        description="Download transaction data as CSV",
        origin=RequirementOrigin.SOURCE_SUPPORTED,
        is_confirmed=True,
        requires_confirmation=False,
    )
    ai_recommendation = ProductRequirement(
        requirement_id="REQ-002",
        title="Email Notifications on Export Completion",
        description="Send email notification when export file is ready",
        origin=RequirementOrigin.AI_RECOMMENDATION,
        is_confirmed=False,
        requires_confirmation=True,
    )
    assert confirmed_req.is_confirmed != ai_recommendation.is_confirmed
    assert confirmed_req.origin != ai_recommendation.origin
    assert ai_recommendation.requires_confirmation is True


def test_unsupported_numerical_targets_not_confirmed():
    """Verify unsupported numerical targets are never marked as confirmed commitments."""
    metric = SuccessMetric(
        metric_name="Adoption Rate",
        description="Percentage of active accounts using feature",
        measurement_method="Analytics event tracking rollup",
        suggested_target="30% of active accounts within 60 days",
        target_origin=RequirementOrigin.AI_RECOMMENDATION,
        is_target_confirmed=True,  # Attempting to mark as confirmed must be overridden!
    )
    assert metric.is_target_confirmed is False
    assert metric.requires_target_confirmation is True
    assert metric.target_origin == RequirementOrigin.AI_RECOMMENDATION
    assert metric.is_confirmed is False


def test_unsupported_measurement_periods_not_confirmed():
    """Verify unsupported measurement periods are marked as unconfirmed recommendations."""
    metric = SuccessMetric(
        metric_name="Report Generation Frequency",
        description="Frequency of user report exports",
        measurement_method="Monthly event count",
        measurement_period="60 days post-launch",
        origin=RequirementOrigin.AI_RECOMMENDATION,
    )
    assert metric.is_period_confirmed is False
    assert metric.period_requires_confirmation is True


def test_user_provided_targets_preserved():
    """Verify user-provided targets are preserved and confirmed."""
    user_target = "50% of enterprise accounts adopting within Q4"
    metric = SuccessMetric(
        metric_name="Enterprise Adoption",
        description="Enterprise tier adoption rate",
        measurement_method="Account billing usage telemetry",
        suggested_target=user_target,
        target_origin=RequirementOrigin.USER_PROVIDED,
        origin=RequirementOrigin.USER_PROVIDED,
        is_confirmed=True,
        source_reference="User business goal: Achieve 50% enterprise adoption in Q4",
    )
    assert metric.suggested_target == user_target
    assert metric.target_origin == RequirementOrigin.USER_PROVIDED
    assert metric.is_target_confirmed is True
    assert metric.requires_target_confirmation is False
    assert "User business goal" in metric.source_reference


def test_analytics_supported_targets_retain_source_reference():
    """Verify analytics-supported targets retain their source references."""
    analytics_source = "Daily analytics rollup table: average 12% baseline across active accounts"
    metric = SuccessMetric(
        metric_name="Export Volume",
        description="Total volume of completed exports",
        measurement_method="Database event stream aggregate",
        baseline="12%",
        suggested_target="25%",
        target_origin=RequirementOrigin.SOURCE_SUPPORTED,
        origin=RequirementOrigin.SOURCE_SUPPORTED,
        is_confirmed=True,
        source_reference=analytics_source,
    )
    assert metric.origin == RequirementOrigin.SOURCE_SUPPORTED
    assert metric.is_confirmed is True
    assert metric.is_target_confirmed is True
    assert metric.source_reference == analytics_source
    assert metric.baseline == "12%"


def test_ai_proposed_targets_marked_as_recommendations():
    """Verify AI-proposed targets are marked as recommendations requiring confirmation."""
    metric = SuccessMetric(
        metric_name="Customer Satisfaction Impact",
        description="CSAT score for export workflows",
        measurement_method="Post-export micro-survey",
        suggested_target="CSAT > 4.2 / 5.0 (Proposed AI Target)",
        target_origin=RequirementOrigin.AI_RECOMMENDATION,
        requires_confirmation=True,
    )
    assert metric.target_origin == RequirementOrigin.AI_RECOMMENDATION
    assert metric.is_target_confirmed is False
    assert metric.requires_target_confirmation is True
    assert metric.is_confirmed is False


def test_missing_targets_remain_null():
    """Verify missing targets remain null when no recommendation is generated."""
    metric = SuccessMetric(
        metric_name="Error Rate During Export",
        description="Percentage of failed export jobs",
        measurement_method="Application error log monitoring",
        expected_direction="decrease",
        suggested_target=None,  # No recommendation generated
        target_origin=None,
    )
    assert metric.suggested_target is None
    assert metric.target_origin is None
    assert metric.is_target_confirmed is False
    assert metric.requires_target_confirmation is False


# ---------------------------------------------------------------------------
# Metric Direction & Origin Grounding Verification Tests
# ---------------------------------------------------------------------------

def test_incorrect_churn_direction_corrected_to_decrease():
    """Verify that churn reduction metrics are deterministically corrected to 'decrease'."""
    # When initialized with incorrect direction 'increase', validator corrects to 'decrease'
    metric = SuccessMetric(
        metric_name="Reduce quarterly customer churn to < 2%",
        description="Decrease account cancellations",
        measurement_method="Quarterly churn cohort rate",
        expected_direction="increase",  # Incorrectly supplied
    )
    assert metric.expected_direction == "decrease"
    assert metric.direction_requires_confirmation is False
    assert infer_expected_direction("Customer Churn Rate", current_direction="increase") == "decrease"
    assert infer_expected_direction("Reduce Churn", current_direction="increase") == "decrease"


def test_correct_adoption_direction_is_increase():
    """Verify that feature adoption metrics evaluate to 'increase'."""
    metric = SuccessMetric(
        metric_name="Automated CSV & Excel Export Engine Feature Adoption Rate",
        description="Percentage of active workspace accounts utilizing capability",
        measurement_method="Analytics event tracking rollup",
        expected_direction="increase",
    )
    assert metric.expected_direction == "increase"
    assert metric.direction_requires_confirmation is False
    assert infer_expected_direction("Weekly Active User Adoption") == "increase"
    assert infer_expected_direction("Improve User Retention") == "increase"


def test_correct_error_rate_direction_is_decrease():
    """Verify that error rate metrics evaluate to 'decrease'."""
    metric = SuccessMetric(
        metric_name="API Export Error Rate",
        description="Percentage of requests returning 5xx status codes",
        measurement_method="Server error log telemetry",
        expected_direction="increase",  # Incorrectly supplied
    )
    assert metric.expected_direction == "decrease"
    assert metric.direction_requires_confirmation is False
    assert infer_expected_direction("Export Failure and Error Rate") == "decrease"
    assert infer_expected_direction("System Downtime and Latency") == "decrease"


def test_unknown_metric_direction_not_assumed_increase():
    """Verify that unknown/unclassified metrics do not default to increase and require confirmation."""
    # 1. infer_expected_direction returns None for unclassifiable metric
    assert infer_expected_direction("Custom Proprietary Factor Theta 9") is None
    assert infer_expected_direction("Internal Telemetry Ratio #42", current_direction="increase") is None

    # 2. SuccessMetric sets direction to None and direction_requires_confirmation to True
    metric = SuccessMetric(
        metric_name="Custom Proprietary Factor Theta 9",
        description="Arbitrary internal coefficient",
        measurement_method="Internal calculations",
        expected_direction="increase",  # Attempting to assume increase
    )
    assert metric.expected_direction is None
    assert metric.direction_requires_confirmation is True


def test_maintain_metric_direction_recognized():
    """Verify that maintain/stability metrics evaluate to 'maintain'."""
    metric = SuccessMetric(
        metric_name="Maintain Current Infrastructure Throughput",
        description="Keep steady state operational capacity",
        measurement_method="APM telemetry",
        expected_direction="maintain",
    )
    assert metric.expected_direction == "maintain"
    assert metric.direction_requires_confirmation is False
    assert infer_expected_direction("Maintain Database Performance Stability") == "maintain"


def test_all_recognized_metric_categories_deterministic():
    """Verify all recognized metric categories evaluate to their deterministic directions."""
    # Decreasing categories
    assert infer_expected_direction("API Response Time") == "decrease"
    assert infer_expected_direction("Cost Reduction") == "decrease"
    assert infer_expected_direction("Defect Rate") == "decrease"
    assert infer_expected_direction("Page Bounce Rate") == "decrease"

    # Increasing categories
    assert infer_expected_direction("Net Promoter Score (NPS)") == "increase"
    assert infer_expected_direction("Customer Satisfaction (CSAT)") == "increase"
    assert infer_expected_direction("Enterprise ARR Growth") == "increase"
    assert infer_expected_direction("System Uptime Percentage") == "increase"

    # Maintaining category
    assert infer_expected_direction("Maintain Error Budget") == "maintain"

    # Unknown category
    assert infer_expected_direction("Arbitrary Alpha Metric") is None



def test_user_provided_target_with_matching_source():
    """Verify that user-provided targets matching strategic context are preserved and confirmed."""
    strategic_ctx = ProductStrategicContext(
        business_goals=["Reduce quarterly customer churn to < 2%", "Expand enterprise ARR"],
    )
    feature_group = MagicMock(
        title="Export Engine",
        description="Automated export tool",
        evidence=["Quote 1"],
        pain_points=["Slow exports"],
        themes=["Export"],
    )
    metric = SuccessMetric(
        metric_name="Strategic Objective: Reduce quarterly customer churn to < 2%",
        description="Organizational business goal",
        measurement_method="Business analytics tracking",
        suggested_target="Reduce quarterly customer churn to < 2%",
        target_origin=RequirementOrigin.USER_PROVIDED,
        origin=RequirementOrigin.USER_PROVIDED,
        is_confirmed=True,
        source_reference="User business goal: Reduce quarterly customer churn to < 2%",
    )
    plan_output = ProductPlanningAgentOutput(
        feature_group_id="507f1f77bcf86cd799439011",
        prd=ProductRequirementsDocument(
            title="Export PRD",
            executive_summary="Summary",
            problem_statement="Problem",
            background="Background",
            proposed_solution="Solution",
        ),
        success_metrics=[metric],
    )

    ProductPlanningService.validate_and_sanitize_requirement_origins(
        plan_output=plan_output,
        feature_group=feature_group,
        strategic_context=strategic_ctx,
    )

    validated_metric = plan_output.success_metrics[0]
    assert validated_metric.origin == RequirementOrigin.USER_PROVIDED
    assert validated_metric.is_confirmed is True
    assert validated_metric.is_target_confirmed is True
    assert validated_metric.requires_confirmation is False
    assert validated_metric.expected_direction == "decrease"


def test_user_provided_target_without_matching_source_downgraded():
    """Verify that a target falsely claiming USER_PROVIDED is downgraded when not in strategic context."""
    strategic_ctx = ProductStrategicContext(
        business_goals=["Expand enterprise ARR"],
    )
    feature_group = MagicMock(
        title="Export Engine",
        evidence=[],
        pain_points=[],
        themes=[],
    )
    unmatched_metric = SuccessMetric(
        metric_name="Invented Retention Target",
        description="Unverified goal",
        measurement_method="Analytics",
        suggested_target="Achieve 99% daily retention in 3 days",  # NOT in strategic context
        target_origin=RequirementOrigin.USER_PROVIDED,
        origin=RequirementOrigin.USER_PROVIDED,
        is_confirmed=True,
        source_reference="User business goal: Achieve 99% daily retention in 3 days",
    )
    plan_output = ProductPlanningAgentOutput(
        feature_group_id="507f1f77bcf86cd799439011",
        prd=ProductRequirementsDocument(
            title="Export PRD",
            executive_summary="Summary",
            problem_statement="Problem",
            background="Background",
            proposed_solution="Solution",
        ),
        success_metrics=[unmatched_metric],
    )

    ProductPlanningService.validate_and_sanitize_requirement_origins(
        plan_output=plan_output,
        feature_group=feature_group,
        strategic_context=strategic_ctx,
    )

    downgraded = plan_output.success_metrics[0]
    assert downgraded.origin == RequirementOrigin.AI_RECOMMENDATION
    assert downgraded.is_confirmed is False
    assert downgraded.requires_confirmation is True
    assert downgraded.is_target_confirmed is False
    assert downgraded.requires_target_confirmation is True


def test_source_supported_target_with_valid_analytics_evidence():
    """Verify that source-supported targets with matching evidence retain confirmed status."""
    feature_group = MagicMock(
        title="Export Engine",
        evidence=["Daily analytics rollup table: average 12% baseline across active accounts"],
        pain_points=["Manual copying takes 2.5 hours"],
        themes=["Reporting Automation"],
    )
    metric = SuccessMetric(
        metric_name="Weekly Export Volume",
        description="Volume of exports",
        measurement_method="Database event stream aggregate",
        baseline="12%",
        suggested_target="25%",
        target_origin=RequirementOrigin.SOURCE_SUPPORTED,
        origin=RequirementOrigin.SOURCE_SUPPORTED,
        is_confirmed=True,
        source_reference="Daily analytics rollup table: average 12% baseline across active accounts",
    )
    plan_output = ProductPlanningAgentOutput(
        feature_group_id="507f1f77bcf86cd799439011",
        prd=ProductRequirementsDocument(
            title="Export PRD",
            executive_summary="Summary",
            problem_statement="Problem",
            background="Background",
            proposed_solution="Solution",
        ),
        success_metrics=[metric],
    )

    ProductPlanningService.validate_and_sanitize_requirement_origins(
        plan_output=plan_output,
        feature_group=feature_group,
    )

    validated = plan_output.success_metrics[0]
    assert validated.origin == RequirementOrigin.SOURCE_SUPPORTED
    assert validated.is_confirmed is True
    assert validated.is_target_confirmed is True


def test_source_supported_target_with_fabricated_evidence_downgraded():
    """Verify that source-supported targets with fabricated evidence are downgraded to recommendations."""
    feature_group = MagicMock(
        title="Export Engine",
        evidence=["Actual customer quote: Need CSV export for audits"],
        pain_points=["Audit block"],
        themes=["Compliance"],
    )
    metric = SuccessMetric(
        metric_name="Customer Satisfaction Score",
        description="CSAT score",
        measurement_method="Micro-survey",
        suggested_target="95% CSAT",
        target_origin=RequirementOrigin.SOURCE_SUPPORTED,
        origin=RequirementOrigin.SOURCE_SUPPORTED,
        is_confirmed=True,
        source_reference="Fabricated internal telemetry survey: 95% satisfaction baseline",  # Fabricated!
    )
    plan_output = ProductPlanningAgentOutput(
        feature_group_id="507f1f77bcf86cd799439011",
        prd=ProductRequirementsDocument(
            title="Export PRD",
            executive_summary="Summary",
            problem_statement="Problem",
            background="Background",
            proposed_solution="Solution",
        ),
        success_metrics=[metric],
    )

    ProductPlanningService.validate_and_sanitize_requirement_origins(
        plan_output=plan_output,
        feature_group=feature_group,
    )

    downgraded = plan_output.success_metrics[0]
    assert downgraded.origin == RequirementOrigin.AI_RECOMMENDATION
    assert downgraded.is_confirmed is False
    assert downgraded.requires_confirmation is True
    assert downgraded.is_target_confirmed is False


def test_llm_falsely_claiming_user_provided_origin_downgraded():
    """Verify that LLM-generated requirements falsely labeled USER_PROVIDED are downgraded."""
    strategic_ctx = ProductStrategicContext(
        technical_constraints=["MongoDB 7.0+", "FastAPI asynchronous back-end"],
    )
    fake_tech_req = TechnicalRequirement(
        title="Kubernetes Auto-scaling Clusters with Istio Service Mesh",
        description="Deploy on GKE with Istio mesh across multi-region VPC.",  # Falsely claimed as user constraint!
        category="architecture",
        rationale="Mandated by organizational strategic context.",
        requires_engineering_review=False,
        origin=RequirementOrigin.USER_PROVIDED,
        is_confirmed=True,
        source_reference="User technical constraint: Kubernetes Auto-scaling Clusters",
    )
    plan_output = ProductPlanningAgentOutput(
        feature_group_id="507f1f77bcf86cd799439011",
        prd=ProductRequirementsDocument(
            title="Export PRD",
            executive_summary="Summary",
            problem_statement="Problem",
            background="Background",
            proposed_solution="Solution",
        ),
        technical_requirements=[fake_tech_req],
    )

    ProductPlanningService.validate_and_sanitize_requirement_origins(
        plan_output=plan_output,
        feature_group=MagicMock(evidence=[], pain_points=[], themes=[]),
        strategic_context=strategic_ctx,
    )

    downgraded_tech = plan_output.technical_requirements[0]
    assert downgraded_tech.origin == RequirementOrigin.AI_RECOMMENDATION
    assert downgraded_tech.is_confirmed is False
    assert downgraded_tech.requires_engineering_review is True



