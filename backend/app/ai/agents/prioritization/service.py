"""
ProductMind AI — Prioritization Service
Orchestrates feature group retrieval, workspace authorization, customer demand & sentiment metrics,
qualitative LLM assessment, deterministic scoring & reweighting, ranking, and MongoDB persistence.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from app.ai.agents.prioritization.agent import PrioritizationAgent
from app.ai.agents.prioritization.schemas import (
    AnalyzePrioritizationRequest,
    AnalyzePrioritizationResponse,
    FactorAssessment,
    FactorName,
    FactorWeightConfig,
    PriorityLevel,
    PrioritizationAgentOutput,
    PrioritizationResult,
    ProductAnalyticsData,
    RankPrioritizationRequest,
    RankPrioritizationResponse,
    ThresholdConfig,
)
from app.ai.agents.prioritization.scoring import (
    compute_customer_demand_score,
    compute_urgency_score,
    compute_sentiment_score,
    compute_usage_impact_score,
    calculate_prioritization_score,
    rank_prioritization_results,
)
from app.core.enums import PlatformRole, MembershipStatus
from app.models.analytics import AnalyticsDailyRollup
from app.models.auth import User
from app.models.intelligence import FeatureGroup
from app.models.planning import PrioritizationScenario
from app.repositories import (
    AnalyticsDailyRollupRepository,
    FeatureGroupRepository,
    FeedbackRepository,
    PrioritizationScenarioRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.ai.service.prioritization")


class PrioritizationService:
    """
    Coordinates Prioritization Agent execution with MongoDB repositories,
    deterministic scoring engine, missing data reweighting, and strict workspace isolation.
    """

    def __init__(
        self,
        agent: Optional[PrioritizationAgent] = None,
        prioritization_repo: Optional[PrioritizationScenarioRepository] = None,
        feature_group_repo: Optional[FeatureGroupRepository] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
        workspace_repo: Optional[WorkspaceRepository] = None,
        membership_repo: Optional[WorkspaceMembershipRepository] = None,
        analytics_rollup_repo: Optional[AnalyticsDailyRollupRepository] = None,
    ):
        self.agent = agent or PrioritizationAgent()
        self.prioritization_repo = prioritization_repo
        self.feature_group_repo = feature_group_repo
        self.feedback_repo = feedback_repo
        self.workspace_repo = workspace_repo
        self.membership_repo = membership_repo
        self.analytics_rollup_repo = analytics_rollup_repo

    async def verify_workspace_access(self, user: User, workspace_id: Any) -> None:
        """
        Enforces strict workspace authorization.
        Permits access if user is platform admin, workspace owner, or active member.
        Raises HTTP 403 Forbidden if user lacks workspace access.
        """
        if user.platform_role == PlatformRole.PLATFORM_ADMIN:
            return

        if self.workspace_repo is None or self.membership_repo is None:
            return

        if not ObjectId.is_valid(str(workspace_id)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid workspace ID format: '{workspace_id}'",
            )

        ws_oid = ObjectId(str(workspace_id))
        workspace = await self.workspace_repo.find_by_id(ws_oid)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # Workspace owner check
        if str(workspace.owner_id) == str(user.id):
            return

        # Active membership check
        membership = await self.membership_repo.find_membership(ws_oid, user.id)
        if not membership or membership.status != MembershipStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have active access to this workspace",
            )

    def _scenario_to_result(self, scenario: PrioritizationScenario) -> PrioritizationResult:
        """Converts a persisted PrioritizationScenario model into a PrioritizationResult contract."""
        metadata = scenario.ai_metadata or {}
        pain_point_severity = metadata.get("customer_pain_point_severity", "")

        # Safe enum conversion
        try:
            p_level = PriorityLevel(scenario.priority_level or "Low")
        except Exception:
            p_level = PriorityLevel.LOW

        return PrioritizationResult(
            result_id=str(scenario.id),
            workspace_id=str(scenario.workspace_id),
            feature_group_id=str(scenario.feature_group_id) if scenario.feature_group_id else "",
            group_name=scenario.name,
            final_score=float(scenario.final_score or 0.0),
            priority_level=p_level,
            factor_scores=scenario.factor_scores or {},
            factor_weights=scenario.factor_weights or {},
            coverage_percentage=float(scenario.coverage_percentage or 100.0),
            explanation=scenario.explanation or "",
            customer_pain_point_severity=pain_point_severity,
            implementation_benefits=scenario.implementation_benefits or [],
            delay_risks=scenario.delay_risks or [],
            supporting_evidence=scenario.supporting_evidence or [],
            missing_data=scenario.missing_data or [],
            recommendation=scenario.recommendation or "",
            agent_metadata=metadata,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
        )

    def _generate_recommendation(
        self,
        priority_level: PriorityLevel,
        final_score: float,
        group_name: str,
    ) -> str:
        """Generates clear, actionable recommendation text for product managers."""
        if priority_level == PriorityLevel.CRITICAL:
            return (
                f"Immediate Roadmap Priority. High demand and strategic leverage for '{group_name}' "
                f"warrant scheduling into the upcoming engineering sprint to mitigate acute user friction."
            )
        elif priority_level == PriorityLevel.HIGH:
            return (
                f"Strong Candidate for Near-Term Release. Significant business impact and steady customer interest "
                f"justify prioritizing '{group_name}' in the next planned milestone."
            )
        elif priority_level == PriorityLevel.MEDIUM:
            return (
                f"Moderate Roadmap Priority. '{group_name}' delivers solid quality-of-life value but has lower "
                f"urgency; consider sequencing after critical priorities or grouping with related enhancements."
            )
        else:
            return (
                f"Backlog / Deprioritized. Low composite score ({final_score}/100) suggests deferring '{group_name}' "
                f"until broader customer demand or stronger strategic alignment emerges."
            )

    @staticmethod
    def _coerce_analytics_evidence(raw: Any) -> Optional[ProductAnalyticsData]:
        """Converts raw dict analytics evidence into ProductAnalyticsData when metrics exist."""
        if isinstance(raw, ProductAnalyticsData):
            return raw if raw.is_available else None
        if not isinstance(raw, dict):
            return None

        candidate_keys = {
            "feature_usage_frequency",
            "active_users",
            "adoption_rate",
            "drop_off_rate",
            "user_engagement_score",
            "trend_direction",
            "is_available",
        }
        if not any(raw.get(k) is not None for k in candidate_keys - {"is_available"}):
            return None

        payload = {k: raw[k] for k in candidate_keys if k in raw and raw[k] is not None}
        payload["is_available"] = bool(raw.get("is_available", True))
        try:
            return ProductAnalyticsData(**payload)
        except Exception:
            return None

    @staticmethod
    def _match_feature_name(fm_name: str, search_terms: List[str]) -> bool:
        """Matches an analytics featureName to a FeatureGroup reliably without generic word false positives."""
        norm_fm = fm_name.strip().lower()
        if not norm_fm:
            return False
        for term in search_terms:
            norm_term = term.strip().lower()
            if not norm_term:
                continue
            if norm_fm == norm_term:
                return True
            if len(norm_term) >= 4 and len(norm_fm) >= 4 and (norm_term in norm_fm or norm_fm in norm_term):
                return True
        return False

    @classmethod
    def _extract_analytics_details_from_rollups(
        cls,
        group: FeatureGroup,
        rollups: List[AnalyticsDailyRollup],
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregates feature-matched product usage evidence across workspace daily rollups.
        Returns None if no reliable feature match exists in the workspace rollups.
        """
        if not rollups:
            return None

        raw_terms = (
            [getattr(group, "title", None), getattr(group, "suggested_capability", None), getattr(group, "primary_tag", None)]
            + list(getattr(group, "common_themes", []) or [])
        )
        search_terms = [t.strip() for t in raw_terms if isinstance(t, str) and len(t.strip()) >= 3]
        if not search_terms:
            return None

        matched_name: Optional[str] = None
        total_events = 0
        daily_series: List[int] = []
        observed_days = 0
        latest_unique_users: Optional[int] = None
        latest_adoption: Optional[float] = None
        has_any_actor_coverage = False

        for rollup in rollups:
            candidates = []
            if rollup.ingested_metrics and rollup.ingested_metrics.feature_metrics:
                candidates.extend(rollup.ingested_metrics.feature_metrics)
            if rollup.feature_metrics:
                candidates.extend(rollup.feature_metrics)

            day_events = 0
            day_matched = False
            for fm in candidates:
                fm_name = getattr(fm, "name", "") or ""
                if not cls._match_feature_name(fm_name, search_terms):
                    continue
                if matched_name is None:
                    matched_name = fm_name
                day_matched = True
                day_events += int(getattr(fm, "event_count", 0) or 0)
                u_cnt = getattr(fm, "unique_users", None)
                if u_cnt is not None:
                    latest_unique_users = int(u_cnt)
                    has_any_actor_coverage = True
                adopt = getattr(fm, "adoption_percent", None)
                if adopt is not None:
                    latest_adoption = float(adopt)

            if day_matched:
                observed_days += 1
                total_events += day_events
                daily_series.append(day_events)

        if matched_name is None or total_events <= 0:
            return None

        # Compute feature-specific trend across observed days
        if len(daily_series) >= 2:
            if daily_series[-1] > daily_series[0]:
                trend_dir = "increasing"
            elif daily_series[-1] < daily_series[0]:
                trend_dir = "decreasing"
            else:
                trend_dir = "stable"
        else:
            trend_dir = "stable"

        # Optional funnel drop-off from latest rollup if measured
        latest = rollups[-1]
        drop_off_rate = None
        if latest.funnel_metrics:
            drop_rates = [
                float(f.drop_off_rate)
                for f in latest.funnel_metrics
                if getattr(f, "drop_off_rate", None) is not None and f.drop_off_rate > 0
            ]
            if drop_rates:
                drop_off_rate = round(max(drop_rates), 2)

        analytics_data = ProductAnalyticsData(
            feature_usage_frequency=float(total_events),
            active_users=latest_unique_users,
            adoption_rate=latest_adoption,
            drop_off_rate=drop_off_rate,
            trend_direction=trend_dir,
            is_available=True,
        )
        return {
            "analytics_data": analytics_data,
            "matched_feature": matched_name,
            "event_count": total_events,
            "unique_users": latest_unique_users,
            "adoption_rate": latest_adoption,
            "drop_off_rate": drop_off_rate,
            "trend_direction": trend_dir,
            "observed_days": observed_days,
            "coverage_status": "complete" if (has_any_actor_coverage and latest_adoption is not None) else "partial",
        }

    @classmethod
    def _extract_analytics_from_rollups(
        cls,
        group: FeatureGroup,
        rollups: List[AnalyticsDailyRollup],
    ) -> Optional[ProductAnalyticsData]:
        """Builds ProductAnalyticsData from persisted workspace analytics rollups when a feature matches."""
        details = cls._extract_analytics_details_from_rollups(group, rollups)
        return details["analytics_data"] if details else None

    async def _resolve_analytics_with_provenance(
        self,
        group: FeatureGroup,
        request: AnalyzePrioritizationRequest,
        rollups_cache: Optional[List[AnalyticsDailyRollup]],
    ) -> Dict[str, Any]:
        """Resolves ProductAnalyticsData plus structured evidence provenance."""
        group_id_str = str(group.id)

        if request.analytics_data and group_id_str in request.analytics_data:
            candidate = request.analytics_data[group_id_str]
            if candidate and candidate.is_available:
                return {
                    "analytics_data": candidate,
                    "matched_feature": group.title,
                    "event_count": int(candidate.feature_usage_frequency) if candidate.feature_usage_frequency is not None else None,
                    "unique_users": candidate.active_users,
                    "adoption_rate": candidate.adoption_rate,
                    "drop_off_rate": candidate.drop_off_rate,
                    "trend_direction": candidate.trend_direction,
                    "observed_days": None,
                    "coverage_status": "complete" if (candidate.active_users is not None and candidate.adoption_rate is not None) else "partial",
                }

        if request.usage_analytics_evidence and isinstance(request.usage_analytics_evidence, dict):
            evidence = request.usage_analytics_evidence
            target = evidence.get(group_id_str, evidence)
            coerced = self._coerce_analytics_evidence(target)
            if coerced:
                return {
                    "analytics_data": coerced,
                    "matched_feature": group.title,
                    "event_count": int(coerced.feature_usage_frequency) if coerced.feature_usage_frequency is not None else None,
                    "unique_users": coerced.active_users,
                    "adoption_rate": coerced.adoption_rate,
                    "drop_off_rate": coerced.drop_off_rate,
                    "trend_direction": coerced.trend_direction,
                    "observed_days": None,
                    "coverage_status": "complete" if (coerced.active_users is not None and coerced.adoption_rate is not None) else "partial",
                }

        if rollups_cache:
            details = self._extract_analytics_details_from_rollups(group, rollups_cache)
            if details:
                return details

        return {"analytics_data": None}

    async def _resolve_analytics_data_for_group(
        self,
        group: FeatureGroup,
        request: AnalyzePrioritizationRequest,
        rollups_cache: Optional[List[AnalyticsDailyRollup]],
    ) -> Optional[ProductAnalyticsData]:
        """Resolves verified product analytics from request overrides, evidence, or persisted MongoDB rollups."""
        group_id_str = str(group.id)

        if request.analytics_data and group_id_str in request.analytics_data:
            candidate = request.analytics_data[group_id_str]
            if candidate and candidate.is_available:
                return candidate

        if request.usage_analytics_evidence and isinstance(request.usage_analytics_evidence, dict):
            evidence = request.usage_analytics_evidence
            if group_id_str in evidence:
                coerced = self._coerce_analytics_evidence(evidence[group_id_str])
                if coerced:
                    return coerced
            coerced = self._coerce_analytics_evidence(evidence)
            if coerced:
                return coerced

        if rollups_cache:
            return self._extract_analytics_from_rollups(group, rollups_cache)

        return None

    async def analyze_prioritization(
        self,
        request: AnalyzePrioritizationRequest,
        user: User,
    ) -> AnalyzePrioritizationResponse:
        """
        Prioritizes feature groups within a workspace:
        1. Verifies workspace access.
        2. Retrieves target FeatureGroup records.
        3. For each group, computes deterministic customer demand, urgency, and sentiment scores.
        4. Evaluates qualitative business impact and strategic alignment via PrioritizationAgent.
        5. Computes final composite score using deterministic scoring engine with missing-data reweighting.
        6. Persists/updates results in prioritization_scenarios collection.
        7. Returns ranked results descending by final composite score.
        """
        start_perf = time.perf_counter()
        await self.verify_workspace_access(user, request.workspace_id)
        ws_oid = ObjectId(request.workspace_id)

        # 1. Fetch candidate FeatureGroup entities
        target_groups: List[FeatureGroup] = []
        if request.feature_group_ids:
            for fg_id_str in request.feature_group_ids:
                if ObjectId.is_valid(fg_id_str) and self.feature_group_repo:
                    fg = await self.feature_group_repo.find_by_id(ObjectId(fg_id_str))
                    if fg and str(fg.workspace_id) == str(ws_oid):
                        target_groups.append(fg)
        else:
            if self.feature_group_repo:
                target_groups = await self.feature_group_repo.find_by_workspace(
                    ws_oid,
                    filter_query={"status": {"$ne": "archived"}},
                    limit=50,
                )

        if not target_groups:
            logger.info("No feature groups found for prioritization in workspace %s", request.workspace_id)
            return AnalyzePrioritizationResponse(
                workspace_id=request.workspace_id,
                total_evaluated=0,
                results=[],
                execution_metadata={
                    "total_evaluated": 0,
                    "elapsed_ms": round((time.perf_counter() - start_perf) * 1000.0, 2),
                },
            )

        rollups_cache: Optional[List[AnalyticsDailyRollup]] = None
        if self.analytics_rollup_repo and not request.analytics_data and not request.usage_analytics_evidence:
            try:
                rollups_cache = await self.analytics_rollup_repo.find_by_workspace(
                    ws_oid,
                    sort=[("date", 1)],
                    limit=30,
                )
            except Exception as exc:
                logger.warning("Failed to query analytics rollups for workspace %s: %s", request.workspace_id, exc)
                rollups_cache = None

        resolved_strategic_ctx = request.strategic_context
        if resolved_strategic_ctx is None and request.strategic_alignment_context:
            resolved_strategic_ctx = StrategicContext(
                primary_business_goals=[request.strategic_alignment_context],
            )

        results: List[PrioritizationResult] = []

        for group in target_groups:
            group_id_str = str(group.id)

            # Check if an active result already exists (unless force_reanalyze is True)
            if not (request.force_reanalyze or request.force_recalculate) and self.prioritization_repo:
                existing_scenario = await self.prioritization_repo.find_by_workspace_and_feature_group(
                    workspace_id=ws_oid,
                    feature_group_id=group.id,
                )
                if existing_scenario:
                    results.append(self._scenario_to_result(existing_scenario))
                    continue

            # 2. Extract & calculate deterministic factor scores
            feedback_count = group.feedback_count
            unique_customer_count = group.unique_customer_count or 1
            if unique_customer_count <= 0 and feedback_count > 0:
                unique_customer_count = 1

            urgency_dist = group.urgency_distribution or {}
            sentiment_dist = {}
            if group.sentiment_distribution:
                sentiment_dist = {
                    "Positive": group.sentiment_distribution.positive,
                    "Neutral": group.sentiment_distribution.neutral,
                    "Negative": group.sentiment_distribution.negative,
                }

            # Factor: Customer Demand (0-100)
            customer_demand_score = compute_customer_demand_score(
                feedback_count=feedback_count,
                unique_customer_count=unique_customer_count,
            )

            # Factor: Urgency (0-100)
            urgency_score = compute_urgency_score(urgency_dist)

            # Factor: Sentiment Friction (0-100)
            sentiment_score = compute_sentiment_score(sentiment_dist)

            # Factor: Usage Impact (0-100 or None)
            usage_resolution = await self._resolve_analytics_with_provenance(
                group=group,
                request=request,
                rollups_cache=rollups_cache,
            )
            analytics_data = usage_resolution.get("analytics_data")
            usage_impact_score = compute_usage_impact_score(analytics_data)

            # 3. Invoke LLM for qualitative evaluation (Business Impact & Strategic Alignment)
            pain_points = group.pain_points or []
            evidence = group.evidence or []

            llm_result = await self.agent.aevaluate(
                group_id=group_id_str,
                title=group.title,
                description=group.description,
                pain_points=pain_points,
                evidence=evidence,
                feedback_count=feedback_count,
                unique_customer_count=unique_customer_count,
                urgency_dist=urgency_dist,
                sentiment_dist=sentiment_dist,
                strategic_context=resolved_strategic_ctx,
                analytics_data=analytics_data,
            )

            qual_eval: PrioritizationAgentOutput = llm_result.data

            # 4. Deterministic Composite Scoring via Scoring Engine
            factor_scores: Dict[str, Optional[float]] = {
                FactorName.CUSTOMER_DEMAND.value: customer_demand_score,
                FactorName.URGENCY.value: urgency_score,
                FactorName.BUSINESS_IMPACT.value: qual_eval.business_impact_score,
                FactorName.STRATEGIC_ALIGNMENT.value: qual_eval.strategic_alignment_score,
                FactorName.SENTIMENT.value: sentiment_score,
                FactorName.USAGE_IMPACT.value: usage_impact_score,
            }

            score_data = calculate_prioritization_score(
                factor_scores=factor_scores,
                weights=request.weight_config,
                thresholds=request.threshold_config,
            )

            final_score = score_data["final_score"]
            priority_level: PriorityLevel = score_data["priority_level"]
            normalized_weights: Dict[str, float] = score_data["normalized_weights"]
            coverage_percentage: float = score_data["coverage_percentage"]
            missing_data: List[str] = score_data["missing_data"]

            # Grounded composite explanation
            usage_str = f"{usage_impact_score}/100" if usage_impact_score is not None else "Unmeasured (reweighted)"
            explanation = (
                f"Demand: {customer_demand_score}/100, Urgency: {urgency_score}/100, "
                f"Business Impact: {qual_eval.business_impact_score}/100, "
                f"Strategic Alignment: {qual_eval.strategic_alignment_score}/100, "
                f"Sentiment Friction: {sentiment_score}/100, Usage Impact: {usage_str}. "
                f"{qual_eval.reasoning}"
            )

            recommendation = self._generate_recommendation(
                priority_level=priority_level,
                final_score=final_score,
                group_name=group.title,
            )

            usage_evidence_summary: Dict[str, Any] = (
                {
                    "available": True,
                    "matched_feature": usage_resolution.get("matched_feature"),
                    "event_count": usage_resolution.get("event_count"),
                    "unique_users": usage_resolution.get("unique_users"),
                    "adoption_rate": usage_resolution.get("adoption_rate"),
                    "drop_off_rate": usage_resolution.get("drop_off_rate"),
                    "trend_direction": usage_resolution.get("trend_direction"),
                    "observed_days": usage_resolution.get("observed_days"),
                    "coverage_status": usage_resolution.get("coverage_status"),
                    "usage_impact_score": usage_impact_score,
                    "weight_applied": normalized_weights.get(FactorName.USAGE_IMPACT.value, 0.0),
                }
                if usage_impact_score is not None and analytics_data is not None
                else {
                    "available": False,
                    "matched_feature": None,
                    "usage_impact_score": None,
                    "weight_applied": 0.0,
                    "missing_reason": "No matching feature usage telemetry found in workspace MongoDB Atlas rollups; weight reweighted across available factors.",
                }
            )

            ai_metadata: Dict[str, Any] = {
                "agent_id": self.agent.agent_id,
                "provider": llm_result.metadata.provider,
                "model": llm_result.metadata.model,
                "latency_ms": llm_result.metadata.latency_ms,
                "customer_pain_point_severity": qual_eval.customer_pain_point_severity,
                "product_opportunity": qual_eval.product_opportunity,
                "business_impact_explanation": qual_eval.business_impact_explanation,
                "strategic_alignment_explanation": qual_eval.strategic_alignment_explanation,
                "usage_analytics_evidence": usage_evidence_summary,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

            # 5. Persist or update in prioritization_scenarios collection
            scenario_doc = None
            if self.prioritization_repo:
                # Find if previous doc exists
                existing = await self.prioritization_repo.find_by_workspace_and_feature_group(
                    workspace_id=ws_oid,
                    feature_group_id=group.id,
                )
                if existing:
                    existing.final_score = final_score
                    existing.priority_level = priority_level.value
                    existing.factor_scores = {k: v for k, v in factor_scores.items() if v is not None}
                    existing.factor_weights = normalized_weights
                    existing.coverage_percentage = coverage_percentage
                    existing.explanation = explanation
                    existing.implementation_benefits = qual_eval.implementation_benefits
                    existing.delay_risks = qual_eval.delay_risks
                    existing.supporting_evidence = qual_eval.supporting_evidence
                    existing.missing_data = missing_data
                    existing.recommendation = recommendation
                    existing.ai_metadata = ai_metadata
                    existing.version += 1
                    existing.updated_at = datetime.now(timezone.utc)
                    update_fields = {
                        "finalScore": existing.final_score,
                        "priorityLevel": existing.priority_level,
                        "factorScores": existing.factor_scores,
                        "factorWeights": existing.factor_weights,
                        "coveragePercentage": existing.coverage_percentage,
                        "explanation": existing.explanation,
                        "implementationBenefits": existing.implementation_benefits,
                        "delayRisks": existing.delay_risks,
                        "supportingEvidence": existing.supporting_evidence,
                        "missingData": existing.missing_data,
                        "recommendation": existing.recommendation,
                        "aiMetadata": existing.ai_metadata,
                        "version": existing.version,
                    }
                    updated_doc = await self.prioritization_repo.update(
                        existing.id,
                        update_fields,
                        workspace_id=ws_oid,
                    )
                    scenario_doc = updated_doc or existing
                else:
                    new_scenario = PrioritizationScenario(
                        workspace_id=ws_oid,
                        name=group.title,
                        description=group.description or "",
                        created_by=user.id,
                        feature_group_id=group.id,
                        final_score=final_score,
                        priority_level=priority_level.value,
                        factor_scores={k: v for k, v in factor_scores.items() if v is not None},
                        factor_weights=normalized_weights,
                        coverage_percentage=coverage_percentage,
                        explanation=explanation,
                        implementation_benefits=qual_eval.implementation_benefits,
                        delay_risks=qual_eval.delay_risks,
                        supporting_evidence=qual_eval.supporting_evidence,
                        missing_data=missing_data,
                        recommendation=recommendation,
                        ai_metadata=ai_metadata,
                        is_active=True,
                    )
                    scenario_doc = await self.prioritization_repo.create(new_scenario)

            if scenario_doc:
                result_item = self._scenario_to_result(scenario_doc)
            else:
                # Fallback if repo not wired
                result_item = PrioritizationResult(
                    result_id=f"prioritization-{group_id_str}",
                    workspace_id=str(ws_oid),
                    feature_group_id=group_id_str,
                    group_name=group.title,
                    final_score=final_score,
                    priority_level=priority_level,
                    factor_scores={k: v for k, v in factor_scores.items() if v is not None},
                    factor_weights=normalized_weights,
                    coverage_percentage=coverage_percentage,
                    explanation=explanation,
                    customer_pain_point_severity=qual_eval.customer_pain_point_severity,
                    implementation_benefits=qual_eval.implementation_benefits,
                    delay_risks=qual_eval.delay_risks,
                    supporting_evidence=qual_eval.supporting_evidence,
                    missing_data=missing_data,
                    recommendation=recommendation,
                    agent_metadata=ai_metadata,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

            results.append(result_item)

        # 6. Rank results descending by final_score
        ranked_results = rank_prioritization_results(results)
        total_time_ms = round((time.perf_counter() - start_perf) * 1000.0, 2)

        return AnalyzePrioritizationResponse(
            workspace_id=request.workspace_id,
            total_evaluated=len(ranked_results),
            results=ranked_results,
            execution_metadata={
                "total_evaluated": len(ranked_results),
                "elapsed_ms": total_time_ms,
            },
        )

    async def get_prioritization_results(
        self,
        workspace_id: str,
        user: User,
        limit: int = 100,
        skip: int = 0,
    ) -> List[PrioritizationResult]:
        """Retrieves active prioritization results for a workspace."""
        await self.verify_workspace_access(user, workspace_id)
        ws_oid = ObjectId(workspace_id)

        if not self.prioritization_repo:
            return []

        scenarios = await self.prioritization_repo.find_active_by_workspace(
            workspace_id=ws_oid,
            limit=limit,
            skip=skip,
        )
        return [self._scenario_to_result(s) for s in scenarios]

    async def get_prioritization_result_by_id(
        self,
        result_id: str,
        workspace_id: str,
        user: User,
    ) -> PrioritizationResult:
        """Retrieves a single prioritization result by its ID."""
        await self.verify_workspace_access(user, workspace_id)

        if not ObjectId.is_valid(result_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid result ID format: '{result_id}'",
            )

        if not self.prioritization_repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prioritization repository unavailable",
            )

        scenario = await self.prioritization_repo.find_by_id(ObjectId(result_id))
        if not scenario or str(scenario.workspace_id) != str(workspace_id) or not scenario.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prioritization result not found",
            )

        return self._scenario_to_result(scenario)

    async def rank_feature_groups(
        self,
        request: RankPrioritizationRequest,
        user: User,
    ) -> RankPrioritizationResponse:
        """
        Ranks existing prioritization results within a workspace:
        Applies descending score sorting, optional min_priority filtering, and top_k capping.
        """
        await self.verify_workspace_access(user, request.workspace_id)
        ws_oid = ObjectId(request.workspace_id)

        if not self.prioritization_repo:
            return RankPrioritizationResponse(
                workspace_id=request.workspace_id,
                total_ranked=0,
                ranked_results=[],
                summary="No prioritization records available.",
            )

        scenarios = await self.prioritization_repo.find_ranked_by_score(
            workspace_id=ws_oid,
            limit=100,
        )

        all_results = [self._scenario_to_result(s) for s in scenarios]

        # Filter by feature_group_ids if provided
        if request.feature_group_ids:
            allowed_fg_ids = set(request.feature_group_ids)
            all_results = [r for r in all_results if r.feature_group_id in allowed_fg_ids]

        # Rank using scoring engine helper
        ranked = rank_prioritization_results(
            all_results,
            top_k=request.top_k,
            min_priority=request.min_priority,
        )

        # Generate summary
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for r in ranked:
            counts[r.priority_level.value] = counts.get(r.priority_level.value, 0) + 1

        summary = (
            f"Ranked {len(ranked)} feature groups: "
            f"{counts['Critical']} Critical, {counts['High']} High, "
            f"{counts['Medium']} Medium, {counts['Low']} Low."
        )

        return RankPrioritizationResponse(
            workspace_id=request.workspace_id,
            total_ranked=len(ranked),
            ranked_results=ranked,
            summary=summary,
        )

