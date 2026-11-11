"""
ProductMind AI — AI Orchestrator Unit Tests
Comprehensive unit tests covering:
- Full 4-stage pipeline execution
- Partial pipeline execution (Mode B)
- Prerequisite dependency validation
- Partial failure isolation and output preservation across all stages
- Workspace authorization and isolation
- Zero feature requests / empty inputs handling
- Missing analytics handling (never zeroed)
- PRD pending review verification
- Execution metadata, timing, and unique run IDs
- In-memory thread-safe run store (caching, retrieval, capacity bounds)
- Health diagnostics
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from app.ai.agents.feedback_intelligence import (
    BatchFeedbackAnalysisResponse,
    BatchFeedbackItemResult,
    FeedbackIntelligenceResult,
    FeedbackClassificationCategory,
    FeedbackSentimentType,
    FeedbackUrgency,
)
from app.ai.agents.feature_intelligence import (
    GroupFeaturesResponse,
    FeatureGroupResult,
)
from app.ai.agents.prioritization import (
    AnalyzePrioritizationResponse,
    PrioritizationResult,
    PriorityLevel,
)
from app.ai.agents.product_planning import (
    ProductPlanResponse,
    ProductRequirementsDocument,
    UserStory,
    AcceptanceCriterion,
)
from app.ai.orchestrator.exceptions import (
    OrchestratorAuthorizationException,
    OrchestratorDependencyException,
    OrchestratorValidationException,
    OrchestratorStageExecutionException,
)
from app.ai.orchestrator.orchestrator import AIOrchestrator
from app.ai.orchestrator.pipeline import PipelineCoordinator
from app.ai.orchestrator.schemas import (
    OrchestratorRequest,
    OrchestratorResponse,
    PipelineMode,
    PipelineStatus,
    StageStatus,
    StageType,
)
from app.ai.orchestrator.state import (
    OrchestratorRunStore,
    PipelineExecutionState,
)
from app.core.enums import PlatformRole
from app.models.auth import User


MOCK_USER_ID = ObjectId("660011223344556677889901")
MOCK_WS_ID = "660011223344556677889902"
MOCK_OTHER_WS_ID = "660011223344556677889999"
MOCK_FB_ID_1 = "660011223344556677889911"
MOCK_FB_ID_2 = "660011223344556677889912"
MOCK_FG_ID = "660011223344556677889921"
MOCK_PRD_ID = "660011223344556677889931"


@pytest.fixture
def mock_user():
    return User(
        id=MOCK_USER_ID,
        name="Lead PM",
        email="pm@productmind.ai",
        password_hash="mock_hash",
        platform_role=PlatformRole.USER,
        is_active=True,
    )


@pytest.fixture
def mock_workspace_repo():
    repo = MagicMock()
    ws = MagicMock()
    ws.id = ObjectId(MOCK_WS_ID)
    ws.name = "Test Workspace"
    ws.owner_id = ObjectId()
    repo.find_by_id = AsyncMock(side_effect=lambda ws_id: ws if str(ws_id) == MOCK_WS_ID else None)
    repo.get_by_id = repo.find_by_id
    return repo


@pytest.fixture
def mock_membership_repo():
    repo = MagicMock()
    mem = MagicMock(role="admin", status="active")
    repo.find_by_workspace_and_user = AsyncMock(
        side_effect=lambda ws_id, user_id: mem if str(ws_id) == MOCK_WS_ID else None
    )
    repo.find_membership = repo.find_by_workspace_and_user
    repo.get_user_membership = repo.find_by_workspace_and_user
    return repo


@pytest.fixture
def mock_feedback_service():
    service = MagicMock()
    analysis_res = FeedbackIntelligenceResult(
        feedback_id=MOCK_FB_ID_1,
        category=FeedbackClassificationCategory.FEATURE_REQUEST,
        sentiment=FeedbackSentimentType.NEUTRAL,
        sentiment_explanation="Customer requested functionality neutrally",
        urgency=FeedbackUrgency.MEDIUM,
        urgency_explanation="Important workflow addition",
        main_theme="Export Functionality",
        customer_pain_point="Cannot export data to CSV",
        summary="Customer wants export option",
        evidence=["Please allow us to export data"],
        suggested_action="Build export feature",
        confidence=0.95,
    )
    item_res = BatchFeedbackItemResult(
        feedback_id=MOCK_FB_ID_1,
        status="success",
        analysis=analysis_res,
    )
    service.analyze_batch = AsyncMock(
        return_value=BatchFeedbackAnalysisResponse(
            total_requested=2,
            successful=2,
            failed=0,
            results=[item_res],
        )
    )
    return service


@pytest.fixture
def mock_feature_service():
    service = MagicMock()
    fg = FeatureGroupResult(
        feature_group_id=MOCK_FG_ID,
        workspace_id=MOCK_WS_ID,
        group_name="CSV & Excel Export Engine",
        feature_summary="Automated data export capabilities",
        consolidated_description="Allows users to export data to CSV and Excel format",
        related_feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
        total_request_count=2,
        unique_customer_count=2,
        sentiment_distribution={"neutral": 2},
        urgency_distribution={"medium": 2},
        common_themes=["export", "reporting"],
        common_pain_points=["no export feature"],
        evidence=["Please allow us to export data"],
        grouping_confidence=0.92,
        grouping_status="suggested",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service.group_feature_requests = AsyncMock(
        return_value=GroupFeaturesResponse(
            workspace_id=MOCK_WS_ID,
            groups_created=1,
            total_feedback_analyzed=2,
            groups=[fg],
            ungrouped_feedback_ids=[],
            execution_metadata={},
        )
    )
    return service


@pytest.fixture
def mock_prioritization_service():
    service = MagicMock()
    p_result = PrioritizationResult(
        result_id="res_123",
        workspace_id=MOCK_WS_ID,
        feature_group_id=MOCK_FG_ID,
        group_name="CSV & Excel Export Engine",
        final_score=85.5,
        priority_level=PriorityLevel.HIGH,
        factor_scores={
            "customer_demand": 80.0,
            "urgency": 75.0,
            "business_impact": 85.0,
            "strategic_alignment": 90.0,
            "sentiment": 70.0,
        },
        factor_weights={
            "customer_demand": 0.25,
            "urgency": 0.15,
            "business_impact": 0.25,
            "strategic_alignment": 0.20,
            "sentiment": 0.15,
        },
        coverage_percentage=100.0,
        explanation="High strategic alignment and demand",
        implementation_benefits=["Enables enterprise reporting"],
        delay_risks=["Potential churn from power users"],
        recommendation="Implement in next sprint",
    )
    service.analyze_prioritization = AsyncMock(
        return_value=AnalyzePrioritizationResponse(
            workspace_id=MOCK_WS_ID,
            total_evaluated=1,
            results=[p_result],
            execution_metadata={},
        )
    )
    return service


@pytest.fixture
def mock_planning_service():
    service = MagicMock()
    plan_response = ProductPlanResponse(
        planning_id=MOCK_PRD_ID,
        workspace_id=MOCK_WS_ID,
        feature_group_id=MOCK_FG_ID,
        prioritization_result_id="scenario_123",
        title="CSV & Excel Export Engine PRD",
        status="pending_review",
        document=ProductRequirementsDocument(
            title="CSV & Excel Export Engine PRD",
            executive_summary="Enables end users to export data to CSV and Excel formats directly from the UI.",
            problem_statement="Users cannot export report data to CSV/Excel.",
            background="Requested by enterprise operations customers.",
            proposed_solution="Implement frontend export button calling streaming backend export endpoints.",
            customer_pain_points=["no export feature"],
            target_users=["Finance and Operations managers"],
            business_objectives=["Reduce churn and increase enterprise reporting adoption"],
            functional_requirements=[],
            non_functional_requirements=[],
            dependencies=[],
            out_of_scope=[],
        ),
        user_stories=[
            UserStory(
                story_id="US-1",
                title="Export transaction table to CSV",
                description="As an Operations Analyst, I want to export transaction tables to CSV, so that I can analyze data in Excel.",
                persona="Operations Analyst",
                business_value="Improves reporting flexibility and efficiency",
                priority="High",
                acceptance_criteria=[
                    AcceptanceCriterion(
                        criterion_id="AC-1",
                        description="Given a filtered transaction table, When user clicks export CSV, Then a CSV file downloads.",
                    )
                ],
            )
        ],
        technical_specifications=[],
        implementation_phases=[],
        risk_matrix=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service.generate_plan = AsyncMock(return_value=plan_response)
    return service


@pytest.fixture
def coordinator(
    mock_feedback_service,
    mock_feature_service,
    mock_prioritization_service,
    mock_planning_service,
):
    return PipelineCoordinator(
        feedback_service=mock_feedback_service,
        feature_service=mock_feature_service,
        prioritization_service=mock_prioritization_service,
        planning_service=mock_planning_service,
    )


@pytest.fixture
def orchestrator(coordinator, mock_workspace_repo, mock_membership_repo):
    run_store = OrchestratorRunStore(capacity=100)
    return AIOrchestrator(
        coordinator=coordinator,
        workspace_repo=mock_workspace_repo,
        membership_repo=mock_membership_repo,
        run_store=run_store,
    )


# --------------------------------------------------------------------------
# 1. Full Pipeline Execution (Mode A)
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_full_pipeline_success(orchestrator, mock_user):
    """Verifies complete sequential execution of all 4 stages in Mode A."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
        strategic_goals=["Accelerate enterprise adoption"],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.COMPLETED
    assert response.mode == PipelineMode.FULL
    assert response.workspace_id == MOCK_WS_ID
    assert response.run_id is not None
    assert len(response.stages) == 4

    # Check each stage succeeded
    for stage in response.stages:
        assert stage.status == StageStatus.COMPLETED
        assert stage.duration_ms >= 0
        assert stage.output is not None

    # Verify stage data handoff
    assert response.feedback_results is not None
    assert response.feature_group_results is not None
    assert response.prioritization_results is not None
    assert response.product_plan_result is not None
    assert response.total_duration_ms >= 0


# --------------------------------------------------------------------------
# 2. Partial Pipeline Execution (Mode B)
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partial_pipeline_prioritization_and_planning(orchestrator, mock_user):
    """Verifies Mode B running only Prioritization and Product Planning."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.PARTIAL,
        stages=[StageType.PRIORITIZATION, StageType.PRODUCT_PLANNING],
        feature_group_ids=[MOCK_FG_ID],
        selected_feature_group_id=MOCK_FG_ID,
        strategic_goals=["Improve reporting"],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.COMPLETED
    assert response.mode == PipelineMode.PARTIAL

    # Verify Stage 1 & 2 skipped, 3 & 4 completed
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEEDBACK_INTELLIGENCE].status == StageStatus.SKIPPED
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.SKIPPED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.COMPLETED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.COMPLETED

    assert response.feedback_results is None
    assert response.feature_group_results is None
    assert response.prioritization_results is not None
    assert response.product_plan_result is not None


@pytest.mark.asyncio
async def test_partial_pipeline_feedback_and_features_only(orchestrator, mock_user):
    """Verifies Mode B running only Feedback Intelligence and Feature Grouping."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.PARTIAL,
        stages=[StageType.FEEDBACK_INTELLIGENCE, StageType.FEATURE_INTELLIGENCE],
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.COMPLETED
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEEDBACK_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.SKIPPED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.SKIPPED


# --------------------------------------------------------------------------
# 3. Prerequisite Dependency Validation
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dependency_validation_missing_feedback_for_feature_grouping(orchestrator, mock_user):
    """Feature Intelligence requested without Stage 1 and without feedback_ids raises error."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.PARTIAL,
        stages=[StageType.FEATURE_INTELLIGENCE],
        feedback_ids=None,
    )

    with pytest.raises(OrchestratorDependencyException) as exc_info:
        await orchestrator.run_pipeline(request=request, user=mock_user)

    assert "requires input 'feedback_ids'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dependency_validation_missing_feature_groups_for_prioritization(orchestrator, mock_user):
    """Prioritization requested without Stage 2 and without feature_group_ids raises error."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.PARTIAL,
        stages=[StageType.PRIORITIZATION],
        feature_group_ids=None,
    )

    with pytest.raises(OrchestratorDependencyException) as exc_info:
        await orchestrator.run_pipeline(request=request, user=mock_user)

    assert "requires input 'feature_group_ids'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dependency_validation_missing_feature_group_for_planning(orchestrator, mock_user):
    """Product Planning requested without Stage 2/3 and without selected feature group raises error."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.PARTIAL,
        stages=[StageType.PRODUCT_PLANNING],
        selected_feature_group_id=None,
        feature_group_ids=None,
    )

    with pytest.raises(OrchestratorDependencyException) as exc_info:
        await orchestrator.run_pipeline(request=request, user=mock_user)

    assert "requires 'selected_feature_group_id'" in str(exc_info.value)


# --------------------------------------------------------------------------
# 4. Partial Failure Isolation and Output Preservation
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_partial_failure_feedback_fails(orchestrator, mock_feedback_service, mock_user):
    """When Stage 1 fails, subsequent stages are skipped and pipeline is FAILED."""
    mock_feedback_service.analyze_batch.side_effect = Exception("LLM connection timeout")

    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.FAILED
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEEDBACK_INTELLIGENCE].status == StageStatus.FAILED
    assert "LLM connection timeout" in stage_map[StageType.FEEDBACK_INTELLIGENCE].error_message
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.SKIPPED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.SKIPPED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.SKIPPED


@pytest.mark.asyncio
async def test_partial_failure_feature_grouping_fails(orchestrator, mock_feature_service, mock_user):
    """When Stage 2 fails, Stage 1 outputs are preserved, status is PARTIALLY_COMPLETED."""
    mock_feature_service.group_feature_requests.side_effect = Exception("Clustering engine error")

    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.PARTIALLY_COMPLETED
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEEDBACK_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.FAILED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.SKIPPED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.SKIPPED

    # Ensure Stage 1 output was preserved!
    assert response.feedback_results is not None
    assert response.feedback_results.successful == 2


@pytest.mark.asyncio
async def test_partial_failure_prioritization_fails(orchestrator, mock_prioritization_service, mock_user):
    """When Stage 3 fails, Stages 1 & 2 outputs are preserved, status is PARTIALLY_COMPLETED."""
    mock_prioritization_service.analyze_prioritization.side_effect = Exception("Scoring failure")

    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.PARTIALLY_COMPLETED
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEEDBACK_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.FAILED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.SKIPPED

    # Ensure Stages 1 & 2 outputs were preserved!
    assert response.feedback_results is not None
    assert response.feature_group_results is not None
    assert len(response.feature_group_results.groups) == 1


@pytest.mark.asyncio
async def test_partial_failure_product_planning_fails(orchestrator, mock_planning_service, mock_user):
    """When Stage 4 fails, Stages 1, 2, 3 outputs are preserved, status is PARTIALLY_COMPLETED."""
    mock_planning_service.generate_plan.side_effect = Exception("PRD generation prompt error")

    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.PARTIALLY_COMPLETED
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEEDBACK_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.COMPLETED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.FAILED

    # Ensure Stages 1, 2, 3 outputs are all preserved!
    assert response.feedback_results is not None
    assert response.feature_group_results is not None
    assert response.prioritization_results is not None
    assert response.product_plan_result is None


# --------------------------------------------------------------------------
# 5. Workspace Isolation and Authorization
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_workspace_authorization_denied(orchestrator, mock_user):
    """User who is not a member of the workspace is rejected."""
    request = OrchestratorRequest(
        workspace_id=MOCK_OTHER_WS_ID,
        mode=PipelineMode.FULL,
    )

    with pytest.raises(OrchestratorAuthorizationException):
        await orchestrator.run_pipeline(request=request, user=mock_user)


# --------------------------------------------------------------------------
# 6. Zero Feature Groups Handling
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_feature_groups_graceful_handling(orchestrator, mock_feature_service, mock_user):
    """When Feature Intelligence finds 0 feature groups, stages 3 & 4 skip cleanly without error."""
    mock_feature_service.group_feature_requests.return_value = GroupFeaturesResponse(
        workspace_id=MOCK_WS_ID,
        groups_created=0,
        total_feedback_analyzed=1,
        groups=[],
        ungrouped_feedback_ids=[MOCK_FB_ID_1],
        execution_metadata={},
    )

    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    # Feature grouping succeeds with 0 groups, stages 3 & 4 skip cleanly
    assert response.status == PipelineStatus.COMPLETED
    stage_map = {s.stage: s for s in response.stages}
    assert stage_map[StageType.FEATURE_INTELLIGENCE].status == StageStatus.COMPLETED
    assert stage_map[StageType.PRIORITIZATION].status == StageStatus.SKIPPED
    assert stage_map[StageType.PRODUCT_PLANNING].status == StageStatus.SKIPPED


# --------------------------------------------------------------------------
# 7. Missing Analytics Handled Properly
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_analytics_handled_properly(orchestrator, mock_prioritization_service, mock_user):
    """Verifies that missing analytics evidence is passed as None without zeroing out."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
        usage_analytics_evidence=None,
    )

    await orchestrator.run_pipeline(request=request, user=mock_user)

    call_args = mock_prioritization_service.analyze_prioritization.call_args[0][0]
    assert call_args.usage_analytics_evidence is None


# --------------------------------------------------------------------------
# 8. PRD Pending Review Verification
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_prd_status_pending_review(orchestrator, mock_user):
    """Verifies that generated product plans have pending_review status (never auto-approved)."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.product_plan_result is not None
    assert response.product_plan_result.status == "pending_review"


# --------------------------------------------------------------------------
# 9. In-Memory Run Store & Retrieval
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_store_caching_and_retrieval(orchestrator, mock_user):
    """Verifies run caching in OrchestratorRunStore and retrieval by ID."""
    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)
    run_id = response.run_id

    # Retrieve from orchestrator
    retrieved = await orchestrator.get_run_by_id(run_id=run_id, user=mock_user)
    assert retrieved is not None
    assert retrieved.run_id == run_id
    assert retrieved.status == PipelineStatus.COMPLETED
    assert retrieved.workspace_id == MOCK_WS_ID


@pytest.mark.asyncio
async def test_run_store_eviction():
    """Verifies bounded memory retention with capacity eviction."""
    store = OrchestratorRunStore(capacity=2)
    now = datetime.now(timezone.utc)
    s1 = OrchestratorResponse(run_id="run_1", workspace_id="ws_1", mode=PipelineMode.FULL, overall_status=PipelineStatus.COMPLETED, started_at=now)
    s2 = OrchestratorResponse(run_id="run_2", workspace_id="ws_1", mode=PipelineMode.FULL, overall_status=PipelineStatus.COMPLETED, started_at=now)
    s3 = OrchestratorResponse(run_id="run_3", workspace_id="ws_1", mode=PipelineMode.FULL, overall_status=PipelineStatus.COMPLETED, started_at=now)

    store.save(s1)
    store.save(s2)
    assert store.size() == 2

    # Adding s3 should evict oldest (s1)
    store.save(s3)
    assert store.size() == 2
    assert store.get("run_1") is None
    assert store.get("run_2") is not None
    assert store.get("run_3") is not None


# --------------------------------------------------------------------------
# 10. Health Diagnostic
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_orchestrator_health_diagnostic(orchestrator):
    """Verifies operational health check and specialist agent connectivity."""
    mock_service = MagicMock()
    mock_service.is_configured = True
    mock_service.settings = MagicMock(AI_PROVIDER="groq", AI_MODEL="qwen/qwen3.8-27b")
    orchestrator.llm_service = mock_service

    health = await orchestrator.get_health()

    assert health.status == "healthy"
    assert health.healthy is True
    assert len(health.specialist_agents) == 4
    for agent in health.specialist_agents:
        assert agent["status"] in ("healthy", "ready")
    assert health.active_runs_cached >= 0


@pytest.mark.asyncio
async def test_orchestrator_translates_product_strategic_context_for_prioritization(
    orchestrator, mock_prioritization_service, mock_user
):
    """Verifies Orchestrator converts ProductStrategicContext cleanly into Prioritization StrategicContext."""
    from app.ai.agents.product_planning.schemas import ProductStrategicContext

    request = OrchestratorRequest(
        workspace_id=MOCK_WS_ID,
        mode=PipelineMode.FULL,
        feedback_ids=[MOCK_FB_ID_1, MOCK_FB_ID_2],
        strategic_context=ProductStrategicContext(
            product_name="ProductMind AI",
            business_goals=["Retain enterprise accounts"],
            target_customer_segments=["Enterprise FinOps"],
            current_quarter_objectives=["Launch warehouse scheduler"],
        ),
    )

    response = await orchestrator.run_pipeline(request=request, user=mock_user)

    assert response.status == PipelineStatus.COMPLETED
    p_req = mock_prioritization_service.analyze_prioritization.call_args[0][0]
    assert p_req.strategic_context is not None
    assert p_req.strategic_context.primary_business_goals == ["Retain enterprise accounts"]
    assert p_req.strategic_context.target_customer_segments == ["Enterprise FinOps"]
    assert p_req.strategic_context.current_quarter_okrs == ["Launch warehouse scheduler"]
