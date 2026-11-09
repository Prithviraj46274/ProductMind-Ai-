"""
ProductMind AI — AI Orchestrator Pipeline Coordinator
Coordinates the 4 specialist AI agents: Feedback Intelligence, Feature Intelligence,
Prioritization, and Product Planning in Full or Partial execution modes.
Handles stage dependency validation, partial failure isolation, and data handoff.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId

from app.models.auth import User
from app.ai.orchestrator.schemas import (
    OrchestratorRequest,
    OrchestratorResponse,
    PipelineMode,
    PipelineStatus,
    StageStatus,
    StageType,
)
from app.ai.orchestrator.exceptions import (
    OrchestratorDependencyException,
    OrchestratorStageExecutionException,
    OrchestratorValidationException,
)
from app.ai.orchestrator.state import PipelineExecutionState
from app.ai.agents.feedback_intelligence.service import FeedbackIntelligenceService
from app.ai.agents.feature_intelligence.service import FeatureIntelligenceService
from app.ai.agents.prioritization.service import PrioritizationService
from app.ai.agents.prioritization.schemas import AnalyzePrioritizationRequest
from app.ai.agents.product_planning.service import ProductPlanningService
from app.ai.agents.product_planning.schemas import GenerateProductPlanRequest
from app.repositories import (
    FeedbackRepository,
    FeatureGroupRepository,
    PrioritizationScenarioRepository,
    PRDRepository,
)

logger = logging.getLogger("productmind.ai.orchestrator.pipeline")


class PipelineCoordinator:
    """
    Executes the sequential multi-agent workflow:
    Stage 1: Feedback Intelligence
    Stage 2: Feature Intelligence
    Stage 3: Prioritization
    Stage 4: Product Planning
    """

    def __init__(
        self,
        feedback_service: FeedbackIntelligenceService,
        feature_service: FeatureIntelligenceService,
        prioritization_service: PrioritizationService,
        planning_service: ProductPlanningService,
        feedback_repo: Optional[FeedbackRepository] = None,
        feature_group_repo: Optional[FeatureGroupRepository] = None,
        prioritization_repo: Optional[PrioritizationScenarioRepository] = None,
        prd_repo: Optional[PRDRepository] = None,
        inter_stage_delay_seconds: float = 0.0,
    ):
        self.feedback_service = feedback_service
        self.feature_service = feature_service
        self.prioritization_service = prioritization_service
        self.planning_service = planning_service
        self.feedback_repo = feedback_repo
        self.feature_group_repo = feature_group_repo
        self.prioritization_repo = prioritization_repo
        self.prd_repo = prd_repo
        self.inter_stage_delay_seconds = inter_stage_delay_seconds

    def resolve_stages_to_run(self, request: OrchestratorRequest) -> List[StageType]:
        """Resolves and validates the ordered list of stages to run."""
        if request.mode == PipelineMode.FULL:
            return [
                StageType.FEEDBACK_INTELLIGENCE,
                StageType.FEATURE_INTELLIGENCE,
                StageType.PRIORITIZATION,
                StageType.PRODUCT_PLANNING,
            ]
        elif request.mode == PipelineMode.PARTIAL:
            if not request.target_stages:
                raise OrchestratorValidationException(
                    "Partial pipeline mode requires 'target_stages' to be explicitly specified",
                    stage="validation",
                )
            # Maintain natural ordering
            canonical_order = [
                StageType.FEEDBACK_INTELLIGENCE,
                StageType.FEATURE_INTELLIGENCE,
                StageType.PRIORITIZATION,
                StageType.PRODUCT_PLANNING,
            ]
            ordered = [st for st in canonical_order if st in request.target_stages]
            if not ordered:
                raise OrchestratorValidationException(
                    "No valid stages specified in target_stages",
                    stage="validation",
                )
            return ordered
        else:
            raise OrchestratorValidationException(
                f"Unsupported pipeline mode: '{request.mode}'",
                stage="validation",
            )

    async def validate_dependencies(
        self,
        stages: List[StageType],
        request: OrchestratorRequest,
        ws_oid: ObjectId,
    ) -> None:
        """Enforces prerequisite validation for requested pipeline stages."""
        # Feature Intelligence requires feedback input if Feedback Intelligence is skipped
        if StageType.FEATURE_INTELLIGENCE in stages and StageType.FEEDBACK_INTELLIGENCE not in stages:
            if not request.feedback_ids:
                if self.feedback_repo:
                    count = await self.feedback_repo.collection.count_documents({"workspaceId": ws_oid})
                    if count == 0:
                        raise OrchestratorDependencyException(
                            "Cannot run Feature Intelligence: requires input 'feedback_ids' or existing feedback items in workspace",
                            stage=StageType.FEATURE_INTELLIGENCE.value,
                        )
                else:
                    raise OrchestratorDependencyException(
                        "Feature Intelligence stage requires input 'feedback_ids' or prior Feedback Intelligence results",
                        stage=StageType.FEATURE_INTELLIGENCE.value,
                    )

        # Prioritization requires feature groups if Feature Intelligence is skipped
        if StageType.PRIORITIZATION in stages and StageType.FEATURE_INTELLIGENCE not in stages:
            if not request.feature_group_ids:
                if self.feature_group_repo:
                    count = await self.feature_group_repo.collection.count_documents({"workspaceId": ws_oid})
                    if count == 0:
                        raise OrchestratorDependencyException(
                            "Cannot run Prioritization: requires input 'feature_group_ids' or existing feature groups in workspace",
                            stage=StageType.PRIORITIZATION.value,
                        )
                else:
                    raise OrchestratorDependencyException(
                        "Prioritization stage requires input 'feature_group_ids' or prior Feature Intelligence results",
                        stage=StageType.PRIORITIZATION.value,
                    )

        # Product Planning requires a feature group if preceding stages are skipped
        if StageType.PRODUCT_PLANNING in stages and StageType.FEATURE_INTELLIGENCE not in stages and StageType.PRIORITIZATION not in stages:
            if not request.selected_feature_group_id and not request.feature_group_ids:
                if self.feature_group_repo:
                    count = await self.feature_group_repo.collection.count_documents({"workspaceId": ws_oid})
                    if count == 0:
                        raise OrchestratorDependencyException(
                            "Product Planning requires 'selected_feature_group_id' or existing feature groups in workspace",
                            stage=StageType.PRODUCT_PLANNING.value,
                        )
                else:
                    raise OrchestratorDependencyException(
                        "Product Planning requires 'selected_feature_group_id' or existing feature groups",
                        stage=StageType.PRODUCT_PLANNING.value,
                    )

    async def execute_pipeline(
        self,
        request: OrchestratorRequest,
        user: User,
        state: PipelineExecutionState,
    ) -> OrchestratorResponse:
        """
        Executes pipeline stages sequentially.
        If any stage fails, successful stage outputs are preserved and execution stops.
        """
        ws_oid = ObjectId(request.workspace_id)
        current_feedback_ids: List[str] = list(request.feedback_ids or [])
        current_feature_group_ids: List[str] = list(request.feature_group_ids or [])
        prioritization_lookup: Dict[str, str] = {}  # fg_id -> scenario_id

        # ---------------------------------------------------------------------
        # Stage 1: Feedback Intelligence
        # ---------------------------------------------------------------------
        if StageType.FEEDBACK_INTELLIGENCE in state.stages_to_run:
            state.mark_stage_started(StageType.FEEDBACK_INTELLIGENCE)
            try:
                # 1. Resolve feedback items to analyze
                target_fids = list(current_feedback_ids)
                if not target_fids and self.feedback_repo:
                    # Find unanalyzed or all workspace feedback
                    cursor = self.feedback_repo.collection.find(
                        {"workspaceId": ws_oid},
                        {"_id": 1},
                    ).limit(50)
                    docs = await cursor.to_list(length=50)
                    target_fids = [str(d["_id"]) for d in docs]

                if not target_fids:
                    state.mark_stage_completed(
                        StageType.FEEDBACK_INTELLIGENCE,
                        metadata={"total_analyzed": 0},
                        warning="No feedback items found in workspace to analyze.",
                    )
                    state.feedback_results = []
                else:
                    batch_res = await self.feedback_service.analyze_batch(
                        feedback_ids=target_fids,
                        user=user,
                        force_reanalyze=request.force_reanalyze,
                        concurrency_limit=1,
                    )
                    state.feedback_results = batch_res
                    successful_items = [
                        r.model_dump() for r in batch_res.results if r.status == "success"
                    ]
                    current_feedback_ids = [
                        r["feedback_id"] for r in successful_items
                    ]
                    state.mark_stage_completed(
                        StageType.FEEDBACK_INTELLIGENCE,
                        metadata={
                            "total_requested": batch_res.total_requested,
                            "successful": batch_res.successful,
                            "failed": batch_res.failed,
                        },
                        warning=f"{batch_res.failed} items failed analysis" if batch_res.failed > 0 else None,
                    )
                    if self.inter_stage_delay_seconds > 0:
                        await asyncio.sleep(self.inter_stage_delay_seconds)
            except Exception as exc:
                logger.exception("Stage 1 (Feedback Intelligence) failed: %s", exc)
                state.mark_stage_failed(StageType.FEEDBACK_INTELLIGENCE, str(exc))
                self._skip_remaining_stages(state, StageType.FEEDBACK_INTELLIGENCE, "Preceding Feedback Intelligence stage failed")
                return state.finalize()

        # ---------------------------------------------------------------------
        # Stage 2: Feature Intelligence
        # ---------------------------------------------------------------------
        if StageType.FEATURE_INTELLIGENCE in state.stages_to_run:
            state.mark_stage_started(StageType.FEATURE_INTELLIGENCE)
            try:
                grouping_fids = current_feedback_ids if current_feedback_ids else None
                group_res = await self.feature_service.group_feature_requests(
                    workspace_id=request.workspace_id,
                    user=user,
                    feedback_ids=grouping_fids,
                    force_regroup=request.force_regroup,
                )
                state.feature_group_results = group_res
                groups_list = getattr(group_res, "groups", None) or getattr(group_res, "feature_groups", None) or []
                raw_groups = [g.model_dump() if hasattr(g, "model_dump") else g for g in groups_list]

                if raw_groups:
                    current_feature_group_ids = [
                        g.get("feature_group_id") if isinstance(g, dict) else getattr(g, "feature_group_id")
                        for g in raw_groups
                    ]
                    state.mark_stage_completed(
                        StageType.FEATURE_INTELLIGENCE,
                        metadata={
                            "total_groups": len(raw_groups),
                            "total_requests_grouped": sum(g.get("total_request_count", 0) if isinstance(g, dict) else getattr(g, "total_request_count", 0) for g in raw_groups),
                        },
                    )
                    if self.inter_stage_delay_seconds > 0:
                        await asyncio.sleep(self.inter_stage_delay_seconds)
                else:
                    state.mark_stage_completed(
                        StageType.FEATURE_INTELLIGENCE,
                        metadata={"total_groups": 0},
                        warning="No eligible feature requests found to group.",
                    )
                    if StageType.PRIORITIZATION in state.stages_to_run:
                        state.mark_stage_skipped(StageType.PRIORITIZATION, "No feature groups available for prioritization")
                    if StageType.PRODUCT_PLANNING in state.stages_to_run:
                        state.mark_stage_skipped(StageType.PRODUCT_PLANNING, "No feature groups available for product planning")
                    return state.finalize()
            except Exception as exc:
                logger.exception("Stage 2 (Feature Intelligence) failed: %s", exc)
                state.mark_stage_failed(StageType.FEATURE_INTELLIGENCE, str(exc))
                self._skip_remaining_stages(state, StageType.FEATURE_INTELLIGENCE, "Preceding Feature Intelligence stage failed")
                return state.finalize()

        # ---------------------------------------------------------------------
        # Stage 3: Prioritization
        # ---------------------------------------------------------------------
        if StageType.PRIORITIZATION in state.stages_to_run:
            state.mark_stage_started(StageType.PRIORITIZATION)
            try:
                target_fg_ids = current_feature_group_ids if current_feature_group_ids else None
                p_request = AnalyzePrioritizationRequest(
                    workspace_id=request.workspace_id,
                    feature_group_ids=target_fg_ids,
                    strategic_context=request.strategic_context,
                    strategic_alignment_context=request.strategic_alignment_context,
                    usage_analytics_evidence=request.usage_analytics_evidence,
                    force_reanalyze=request.force_recalculate_prioritization,
                    force_recalculate=request.force_recalculate_prioritization,
                )
                p_res = await self.prioritization_service.analyze_prioritization(
                    p_request,
                    user,
                )
                state.prioritization_results = p_res

                results_list = getattr(p_res, "results", []) or []
                for r in results_list:
                    fg_id = getattr(r, "feature_group_id", None)
                    if fg_id:
                        prioritization_lookup[fg_id] = getattr(r, "result_id", getattr(r, "scenario_id", None))

                top_r = results_list[0] if results_list else None
                top_priority = getattr(top_r, "priority_level", None) or getattr(top_r, "priority_classification", None) if top_r else None
                if hasattr(top_priority, "value"):
                    top_priority = top_priority.value
                top_score = getattr(top_r, "final_score", None) or getattr(top_r, "priority_score", None) if top_r else None

                state.mark_stage_completed(
                    StageType.PRIORITIZATION,
                    metadata={
                        "total_evaluated": getattr(p_res, "total_evaluated", len(results_list)),
                        "top_priority": str(top_priority) if top_priority else None,
                        "top_score": top_score,
                    },
                )
                if self.inter_stage_delay_seconds > 0:
                    await asyncio.sleep(self.inter_stage_delay_seconds)
            except Exception as exc:
                logger.exception("Stage 3 (Prioritization) failed: %s", exc)
                state.mark_stage_failed(StageType.PRIORITIZATION, str(exc))
                self._skip_remaining_stages(state, StageType.PRIORITIZATION, "Preceding Prioritization stage failed")
                return state.finalize()

        # ---------------------------------------------------------------------
        # Stage 4: Product Planning
        # ---------------------------------------------------------------------
        if StageType.PRODUCT_PLANNING in state.stages_to_run:
            state.mark_stage_started(StageType.PRODUCT_PLANNING)
            try:
                # Resolve target feature group to plan
                target_planning_fg_id = request.selected_feature_group_id
                if not target_planning_fg_id:
                    # Top-ranked from Stage 3
                    if state.prioritization_results:
                        p_res = state.prioritization_results
                        p_list = getattr(p_res, "results", p_res if isinstance(p_res, list) else [])
                        if p_list:
                            first_p = p_list[0]
                            target_planning_fg_id = getattr(first_p, "feature_group_id", None) or (first_p.get("feature_group_id") if isinstance(first_p, dict) else None)
                    # Or first from Stage 2
                    elif state.feature_group_results:
                        fg_res = state.feature_group_results
                        fg_list = getattr(fg_res, "groups", fg_res if isinstance(fg_res, list) else [])
                        if fg_list:
                            first_fg = fg_list[0]
                            target_planning_fg_id = getattr(first_fg, "feature_group_id", None) or (first_fg.get("feature_group_id") if isinstance(first_fg, dict) else None)
                    # Or first from request
                    elif current_feature_group_ids:
                        target_planning_fg_id = current_feature_group_ids[0]

                if not target_planning_fg_id:
                    state.mark_stage_completed(
                        StageType.PRODUCT_PLANNING,
                        metadata={"planning_id": None},
                        warning="Skipped Product Planning: no feature group selected or eligible to plan.",
                    )
                else:
                    matched_p_id = prioritization_lookup.get(target_planning_fg_id)
                    plan_req = GenerateProductPlanRequest(
                        workspace_id=request.workspace_id,
                        feature_group_id=target_planning_fg_id,
                        prioritization_result_id=matched_p_id,
                        strategic_context=request.strategic_context,
                        force_approved_overwrite=request.force_approved_overwrite,
                    )
                    plan_res = await self.planning_service.generate_plan(
                        request=plan_req,
                        user=user,
                    )
                    state.planning_result = plan_res
                    doc = getattr(plan_res, "prd", None) or getattr(plan_res, "document", None)
                    fn_req_count = len(doc.functional_requirements) if doc and hasattr(doc, "functional_requirements") and doc.functional_requirements else 0
                    stories_count = len(plan_res.user_stories) if hasattr(plan_res, "user_stories") and plan_res.user_stories else 0
                    state.mark_stage_completed(
                        StageType.PRODUCT_PLANNING,
                        metadata={
                            "planning_id": plan_res.planning_id,
                            "title": plan_res.title,
                            "status": plan_res.status,
                            "user_stories_count": stories_count,
                            "functional_requirements_count": fn_req_count,
                        },
                    )
            except Exception as exc:
                logger.exception("Stage 4 (Product Planning) failed: %s", exc)
                state.mark_stage_failed(StageType.PRODUCT_PLANNING, str(exc))
                return state.finalize()

        return state.finalize()

    def _skip_remaining_stages(
        self,
        state: PipelineExecutionState,
        failed_stage: StageType,
        reason: str,
    ) -> None:
        """Skips subsequent stages when a prerequisite stage fails."""
        idx = state.stages_to_run.index(failed_stage)
        for subsequent in state.stages_to_run[idx + 1:]:
            state.mark_stage_skipped(subsequent, reason)

