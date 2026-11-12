"""
ProductMind AI — Phase 4.2: Workspace Context Retrieval Service
Retrieves bounded, workspace-scoped summaries from MongoDB Atlas across all five
product intelligence domains for future Conversational Copilot consumption.
"""

from datetime import datetime, timezone
import json
import math
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.endpoints.analytics import (
    _can_report_distinct_ids,
    _coverage,
    _metrics_from_rollups,
    _resolve_date_range,
)
from app.core.enums import MembershipStatus, PlatformRole
from app.models.auth import User, Workspace
from app.repositories import (
    AnalyticsDailyRollupRepository,
    AnalyticsEventRepository,
    FeatureGroupRepository,
    FeedbackRepository,
    PRDRepository,
    PrioritizationScenarioRepository,
    RoadmapRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)


MAX_FEEDBACK_ITEMS = 10
MAX_FEATURE_GROUPS = 10
MAX_PAIN_POINTS_PER_GROUP = 2
MAX_PRIORITIZATION_ITEMS = 10
MAX_ANALYTICS_FEATURES = 8
MAX_PRDS = 5
MAX_ROADMAP_ITEMS = 8
MAX_DESCRIPTION_CHARS = 160
MAX_EXPLANATION_CHARS = 240


def _truncate(text: Optional[str], max_len: int = MAX_DESCRIPTION_CHARS) -> str:
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max(0, max_len - 3)].rstrip() + "..."


_STOPWORDS = {
    "what", "which", "where", "when", "why", "how", "are", "is", "the", "our", "for",
    "and", "with", "from", "that", "this", "have", "has", "should", "next", "most",
    "about", "based", "data", "workspace", "customer", "customers", "product",
    "feature", "features", "feedback", "analytics", "prioritize", "priority",
    "roadmap", "prd", "prds", "can", "you", "tell", "show", "explain", "compare",
}


def _extract_topic_terms(question: Optional[str]) -> List[str]:
    if not question:
        return []
    words = [w.strip(".,?!:;\"'()[]{}").lower() for w in question.split()]
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS][:6]


def _prioritize_by_terms(items: List[Any], terms: List[str], text_fn) -> List[Any]:
    if not items or not terms:
        return items
    matched = []
    rest = []
    for item in items:
        haystack = (text_fn(item) or "").lower()
        if any(t in haystack for t in terms):
            matched.append(item)
        else:
            rest.append(item)
    return matched + rest


class WorkspaceMetadataContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workspace_id: str = Field(alias="workspaceId")
    name: str
    slug: str
    plan: str
    status: str


class FeedbackContextItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    description: str
    category: Optional[str] = None
    sentiment: Optional[str] = None
    priority: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    feedback_date: Optional[str] = Field(default=None, alias="feedbackDate")


class FeedbackContextSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_count: int = Field(default=0, alias="totalCount")
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict, alias="sentimentDistribution")
    priority_distribution: Dict[str, int] = Field(default_factory=dict, alias="priorityDistribution")
    top_categories: List[Dict[str, Any]] = Field(default_factory=list, alias="topCategories")
    top_themes: List[str] = Field(default_factory=list, alias="topThemes")
    items: List[FeedbackContextItem] = Field(default_factory=list)


class FeatureGroupContextItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    category: Optional[str] = None
    status: Optional[str] = None
    feedback_count: int = Field(default=0, alias="feedbackCount")
    unique_customer_count: Optional[int] = Field(default=None, alias="uniqueCustomerCount")
    pain_points: List[str] = Field(default_factory=list, alias="painPoints")
    common_themes: List[str] = Field(default_factory=list, alias="commonThemes")
    sentiment_distribution: Dict[str, int] = Field(default_factory=dict, alias="sentimentDistribution")


class FeatureIntelligenceContextSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_count: int = Field(default=0, alias="totalCount")
    items: List[FeatureGroupContextItem] = Field(default_factory=list)


class PrioritizationContextItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")
    final_score: Optional[float] = Field(default=None, alias="finalScore")
    priority_level: Optional[str] = Field(default=None, alias="priorityLevel")
    factor_scores: Dict[str, float] = Field(default_factory=dict, alias="factorScores")
    factor_weights: Dict[str, float] = Field(default_factory=dict, alias="factorWeights")
    coverage_percentage: float = Field(default=100.0, alias="coveragePercentage")
    missing_data: List[str] = Field(default_factory=list, alias="missingData")
    usage_analytics_evidence: Optional[Dict[str, Any]] = Field(default=None, alias="usageAnalyticsEvidence")
    explanation: Optional[str] = None


class PrioritizationContextSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_count: int = Field(default=0, alias="totalCount")
    items: List[PrioritizationContextItem] = Field(default_factory=list)


class AnalyticsFeatureContextItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    event_count: int = Field(alias="eventCount")
    unique_users: Optional[int] = Field(default=None, alias="uniqueUsers")
    adoption_percent: Optional[float] = Field(default=None, alias="adoptionPercent")


class ProductAnalyticsContextSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    time_range: str = Field(default="30d", alias="timeRange")
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    total_events: int = Field(default=0, alias="totalEvents")
    active_users: Optional[int] = Field(default=None, alias="activeUsers")
    total_sessions: Optional[int] = Field(default=None, alias="totalSessions")
    avg_event_duration_seconds: Optional[float] = Field(default=None, alias="avgEventDurationSeconds")
    coverage_state: str = Field(default="no_data", alias="coverageState")
    observed_days: int = Field(default=0, alias="observedDays")
    top_features: List[AnalyticsFeatureContextItem] = Field(default_factory=list, alias="topFeatures")


class PRDContextItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    status: str
    version: str
    problem_statement: str = Field(default="", alias="problemStatement")
    objectives: str = ""
    user_stories_count: int = Field(default=0, alias="userStoriesCount")
    user_story_titles: List[str] = Field(default_factory=list, alias="userStoryTitles")
    success_metrics: List[str] = Field(default_factory=list, alias="successMetrics")


class RoadmapContextItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    status: str
    priority: str
    quarter: Optional[str] = None
    start_date: str = Field(alias="startDate")
    target_date: str = Field(alias="targetDate")
    progress: float = 0.0


class ProductPlanningContextSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_prds: int = Field(default=0, alias="totalPrds")
    prds: List[PRDContextItem] = Field(default_factory=list)
    total_roadmap_items: int = Field(default=0, alias="totalRoadmapItems")
    roadmap_items: List[RoadmapContextItem] = Field(default_factory=list, alias="roadmapItems")


class ContextRetrievalMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    retrieved_at: datetime = Field(alias="retrievedAt")
    limits_applied: Dict[str, int] = Field(alias="limitsApplied")
    estimated_chars: int = Field(default=0, alias="estimatedChars")
    estimated_tokens: int = Field(default=0, alias="estimatedTokens")
    missing_domains: List[str] = Field(default_factory=list, alias="missingDomains")
    partial_signals: List[str] = Field(default_factory=list, alias="partialSignals")
    data_limitations: List[str] = Field(default_factory=list, alias="dataLimitations")
    cross_domain_links: List[Dict[str, Any]] = Field(default_factory=list, alias="crossDomainLinks")


class WorkspaceCopilotContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workspace: WorkspaceMetadataContext
    feedback: FeedbackContextSummary
    feature_intelligence: FeatureIntelligenceContextSummary = Field(alias="featureIntelligence")
    prioritization: PrioritizationContextSummary
    analytics: ProductAnalyticsContextSummary
    planning: ProductPlanningContextSummary
    metadata: ContextRetrievalMetadata


class CopilotContextService:
    """
    Assembles deterministic, bounded, workspace-scoped context from MongoDB Atlas
    for the ProductMind AI Conversational Copilot.
    """

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        membership_repo: WorkspaceMembershipRepository,
        feedback_repo: FeedbackRepository,
        feature_group_repo: FeatureGroupRepository,
        prioritization_repo: PrioritizationScenarioRepository,
        analytics_event_repo: AnalyticsEventRepository,
        analytics_rollup_repo: AnalyticsDailyRollupRepository,
        prd_repo: PRDRepository,
        roadmap_repo: RoadmapRepository,
    ):
        self.workspace_repo = workspace_repo
        self.membership_repo = membership_repo
        self.feedback_repo = feedback_repo
        self.feature_group_repo = feature_group_repo
        self.prioritization_repo = prioritization_repo
        self.analytics_event_repo = analytics_event_repo
        self.analytics_rollup_repo = analytics_rollup_repo
        self.prd_repo = prd_repo
        self.roadmap_repo = roadmap_repo

    async def _authorize_workspace(self, workspace_id: str, user: User) -> Workspace:
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
        if user.platform_role == PlatformRole.PLATFORM_ADMIN:
            return workspace
        if str(workspace.owner_id) == str(user.id):
            return workspace
        membership = await self.membership_repo.find_membership(ws_oid, user.id)
        if not membership or membership.status != MembershipStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have active access to this workspace",
            )
        return workspace

    async def _retrieve_feedback(self, ws_oid: ObjectId) -> FeedbackContextSummary:
        summary = await self.feedback_repo.summarize_workspace_feedback(ws_oid)
        items_list, _ = await self.feedback_repo.find_page(
            ws_oid,
            page=1,
            limit=MAX_FEEDBACK_ITEMS,
            sort="priority",
        )
        items = [
            FeedbackContextItem(
                id=str(fb.id),
                title=_truncate(fb.title, 120),
                description=_truncate(fb.description, MAX_DESCRIPTION_CHARS),
                category=fb.category.value if hasattr(fb.category, "value") else fb.category,
                sentiment=fb.sentiment.value if hasattr(fb.sentiment, "value") else fb.sentiment,
                priority=(
                    fb.source_priority.value
                    if hasattr(fb.source_priority, "value")
                    else (
                        fb.source_priority
                        or (
                            fb.ai_predicted_priority.value
                            if hasattr(fb.ai_predicted_priority, "value")
                            else fb.ai_predicted_priority
                        )
                    )
                ),
                tags=(fb.ai_themes or fb.tags or [])[:5],
                feedbackDate=fb.feedback_date.date().isoformat() if fb.feedback_date else None,
            )
            for fb in items_list
        ]
        return FeedbackContextSummary(
            totalCount=summary["totalCount"],
            sentimentDistribution=summary["sentimentDistribution"],
            priorityDistribution=summary["priorityDistribution"],
            topCategories=summary["topCategories"],
            topThemes=summary["topThemes"],
            items=items,
        )

    async def _retrieve_feature_intelligence(self, ws_oid: ObjectId) -> FeatureIntelligenceContextSummary:
        total_count = await self.feature_group_repo.count(ws_oid)
        groups = await self.feature_group_repo.find_by_workspace_and_filters(
            ws_oid,
            limit=MAX_FEATURE_GROUPS,
        )
        items = []
        for g in groups:
            s_dist = {}
            if g.sentiment_distribution:
                s_dist = {
                    "Positive": g.sentiment_distribution.positive,
                    "Neutral": g.sentiment_distribution.neutral,
                    "Negative": g.sentiment_distribution.negative,
                }
            items.append(
                FeatureGroupContextItem(
                    id=str(g.id),
                    title=_truncate(g.title, 120),
                    category=g.category.value if hasattr(g.category, "value") else g.category,
                    status=g.status.value if hasattr(g.status, "value") else g.status,
                    feedbackCount=g.feedback_count,
                    uniqueCustomerCount=g.unique_customer_count if g.unique_customer_count else None,
                    painPoints=[_truncate(p, MAX_DESCRIPTION_CHARS) for p in (g.pain_points or [])[:MAX_PAIN_POINTS_PER_GROUP]],
                    commonThemes=(g.common_themes or [])[:5],
                    sentimentDistribution=s_dist,
                )
            )
        return FeatureIntelligenceContextSummary(totalCount=total_count, items=items)

    async def _retrieve_prioritization(self, ws_oid: ObjectId) -> PrioritizationContextSummary:
        total_count = await self.prioritization_repo.count(ws_oid, {"isActive": True})
        scenarios = await self.prioritization_repo.find_ranked_by_score(
            ws_oid,
            limit=MAX_PRIORITIZATION_ITEMS,
        )
        items = [
            PrioritizationContextItem(
                id=str(sc.id),
                name=_truncate(sc.name, 120),
                featureGroupId=str(sc.feature_group_id) if sc.feature_group_id else None,
                finalScore=sc.final_score,
                priorityLevel=sc.priority_level,
                factorScores=sc.factor_scores or {},
                factorWeights=sc.factor_weights or {},
                coveragePercentage=sc.coverage_percentage,
                missingData=sc.missing_data or [],
                usageAnalyticsEvidence=(sc.ai_metadata or {}).get("usage_analytics_evidence"),
                explanation=_truncate(sc.explanation, MAX_EXPLANATION_CHARS) if sc.explanation else None,
            )
            for sc in scenarios
        ]
        return PrioritizationContextSummary(totalCount=total_count, items=items)

    async def _retrieve_analytics(self, ws_oid: ObjectId) -> tuple[ProductAnalyticsContextSummary, List[str]]:
        partial_signals: List[str] = []
        start, end, start_dt, end_ex, _ = _resolve_date_range("30d", None, None)

        raw_metrics = await self.analytics_event_repo.aggregate_range_overview(ws_oid, start_dt, end_ex)
        rollups = await self.analytics_rollup_repo.find_ingested_range(
            ws_oid,
            start.isoformat(),
            end.isoformat(),
        )
        rolled_up = _metrics_from_rollups(rollups)
        raw_is_complete = _can_report_distinct_ids(rolled_up, raw_metrics)
        cov = _coverage(
            rolled_up["totalEvents"],
            rolled_up["eventsWithActorId"],
            rolled_up["eventsWithSessionId"],
            raw_metrics.get("totalEvents", 0),
        )

        active_users = (
            raw_metrics.get("activeUsers")
            if raw_is_complete and rolled_up["eventsWithActorId"] == rolled_up["totalEvents"]
            else None
        )
        total_sessions = (
            raw_metrics.get("totalSessions")
            if raw_is_complete and rolled_up["eventsWithSessionId"] == rolled_up["totalEvents"]
            else None
        )
        if rolled_up["totalEvents"] > 0 and active_users is None:
            partial_signals.append("analytics.activeUsers_unavailable_partial_actor_coverage")
        if rolled_up["totalEvents"] > 0 and total_sessions is None:
            partial_signals.append("analytics.totalSessions_unavailable_partial_session_coverage")

        feature_page = await self.analytics_event_repo.aggregate_feature_page(
            ws_oid,
            start_dt,
            end_ex,
            page=1,
            limit=MAX_ANALYTICS_FEATURES,
        )
        top_features: List[AnalyticsFeatureContextItem] = []
        for metric in feature_page.get("items", []):
            has_user_cov = metric.get("eventsWithActorId") == metric.get("eventCount") and raw_is_complete
            unique_users = metric.get("uniqueUsers") if has_user_cov else None
            adoption = (
                round(unique_users / active_users * 100, 2)
                if unique_users is not None and active_users
                else None
            )
            if metric.get("eventCount", 0) > 0 and adoption is None:
                partial_signals.append(f"analytics.feature_adoption_unavailable:{metric['_id']}")
            top_features.append(
                AnalyticsFeatureContextItem(
                    name=_truncate(metric["_id"], 100),
                    eventCount=int(metric["eventCount"]),
                    uniqueUsers=unique_users,
                    adoptionPercent=adoption,
                )
            )

        summary = ProductAnalyticsContextSummary(
            timeRange="30d",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            totalEvents=rolled_up["totalEvents"],
            activeUsers=active_users,
            totalSessions=total_sessions,
            avgEventDurationSeconds=rolled_up["avgEventDurationSeconds"],
            coverageState=cov.state,
            observedDays=rolled_up["observedDays"],
            topFeatures=top_features,
        )
        return summary, partial_signals

    async def _retrieve_planning(self, ws_oid: ObjectId) -> ProductPlanningContextSummary:
        total_prds = await self.prd_repo.count(ws_oid)
        prd_docs = await self.prd_repo.find_by_workspace_and_filters(ws_oid, limit=MAX_PRDS)
        prds: List[PRDContextItem] = []
        for prd in prd_docs:
            stories_titles: List[str] = []
            for st in (prd.user_stories or [])[:3]:
                if isinstance(st, dict):
                    stories_titles.append(_truncate(st.get("title") or st.get("story") or "", 100))
            metrics_list: List[str] = []
            for sm in (prd.success_metrics or [])[:3]:
                if isinstance(sm, dict):
                    metrics_list.append(_truncate(sm.get("metric") or sm.get("name") or str(sm), 100))
                elif isinstance(sm, str):
                    metrics_list.append(_truncate(sm, 100))

            prds.append(
                PRDContextItem(
                    id=str(prd.id),
                    title=_truncate(prd.title, 120),
                    status=prd.status.value if hasattr(prd.status, "value") else str(prd.status),
                    version=prd.version,
                    problemStatement=_truncate(prd.sections.problem_statement if prd.sections else "", MAX_DESCRIPTION_CHARS),
                    objectives=_truncate(prd.sections.goals_and_success_metrics if prd.sections else "", MAX_DESCRIPTION_CHARS),
                    userStoriesCount=len(prd.user_stories or []),
                    userStoryTitles=[t for t in stories_titles if t],
                    successMetrics=[m for m in metrics_list if m],
                )
            )

        total_roadmap = await self.roadmap_repo.count(ws_oid)
        roadmap_docs = await self.roadmap_repo.find_by_workspace(
            ws_oid,
            sort=[("targetDate", 1)],
            limit=MAX_ROADMAP_ITEMS,
        )
        roadmap_items = [
            RoadmapContextItem(
                id=str(rm.id),
                title=_truncate(rm.title, 120),
                status=rm.status.value if hasattr(rm.status, "value") else str(rm.status),
                priority=rm.priority.value if hasattr(rm.priority, "value") else str(rm.priority),
                quarter=rm.milestone,
                startDate=rm.start_date,
                targetDate=rm.target_date,
                progress=rm.progress,
            )
            for rm in roadmap_docs
        ]
        return ProductPlanningContextSummary(
            totalPrds=total_prds,
            prds=prds,
            totalRoadmapItems=total_roadmap,
            roadmapItems=roadmap_items,
        )

    async def get_workspace_context(
        self,
        workspace_id: str,
        user: User,
        question: Optional[str] = None,
    ) -> WorkspaceCopilotContext:
        """
        Authorizes user access to workspace_id and retrieves bounded summaries
        from all 5 product intelligence domains in MongoDB Atlas.
        """
        workspace = await self._authorize_workspace(workspace_id, user)
        if not workspace.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        ws_oid = workspace.id

        feedback_summary = await self._retrieve_feedback(ws_oid)
        feature_summary = await self._retrieve_feature_intelligence(ws_oid)
        prioritization_summary = await self._retrieve_prioritization(ws_oid)
        analytics_summary, partial_signals = await self._retrieve_analytics(ws_oid)
        planning_summary = await self._retrieve_planning(ws_oid)

        missing_domains: List[str] = []
        if feedback_summary.total_count == 0:
            missing_domains.append("feedback")
        if feature_summary.total_count == 0:
            missing_domains.append("feature_intelligence")
        if prioritization_summary.total_count == 0:
            missing_domains.append("prioritization")
        if analytics_summary.total_events == 0:
            missing_domains.append("analytics")
        if planning_summary.total_prds == 0 and planning_summary.total_roadmap_items == 0:
            missing_domains.append("planning")

        for sc in prioritization_summary.items:
            if "usage_impact" in (sc.missing_data or []):
                partial_signals.append(f"prioritization.usage_impact_missing:{sc.name}")

        # Topic-aware prioritization of retrieved items so question-relevant records stay first
        topic_terms = _extract_topic_terms(question)
        if topic_terms:
            feedback_summary.items = _prioritize_by_terms(
                feedback_summary.items,
                topic_terms,
                lambda x: f"{x.title} {x.description} {' '.join(x.tags)}",
            )
            feature_summary.items = _prioritize_by_terms(
                feature_summary.items,
                topic_terms,
                lambda x: f"{x.title} {' '.join(x.pain_points)} {' '.join(x.common_themes)}",
            )
            prioritization_summary.items = _prioritize_by_terms(
                prioritization_summary.items,
                topic_terms,
                lambda x: f"{x.name} {x.explanation or ''}",
            )
            analytics_summary.top_features = _prioritize_by_terms(
                analytics_summary.top_features,
                topic_terms,
                lambda x: x.name,
            )
            planning_summary.prds = _prioritize_by_terms(
                planning_summary.prds,
                topic_terms,
                lambda x: f"{x.title} {x.problem_statement}",
            )
            planning_summary.roadmap_items = _prioritize_by_terms(
                planning_summary.roadmap_items,
                topic_terms,
                lambda x: x.title,
            )

        # Build verified cross-domain links (without fabricating unverified mappings)
        cross_domain_links: List[Dict[str, Any]] = []
        fg_by_id = {fg.id: fg for fg in feature_summary.items}
        for sc in prioritization_summary.items[:5]:
            link: Dict[str, Any] = {
                "type": "prioritization_link",
                "prioritizationId": sc.id,
                "name": sc.name,
                "finalScore": sc.final_score,
                "analyticsVerified": bool(sc.usage_analytics_evidence),
            }
            if sc.feature_group_id and sc.feature_group_id in fg_by_id:
                fg = fg_by_id[sc.feature_group_id]
                link["featureGroupId"] = fg.id
                link["featureGroupTitle"] = fg.title
                link["feedbackCount"] = fg.feedback_count
            if sc.usage_analytics_evidence:
                link["usageAnalyticsEvidence"] = sc.usage_analytics_evidence
            cross_domain_links.append(link)

        if topic_terms and analytics_summary.total_events == 0 and (
            feedback_summary.items or feature_summary.items
        ):
            cross_domain_links.append(
                {
                    "type": "unverified_analytics_mapping",
                    "topics": topic_terms,
                    "analyticsVerified": False,
                    "reason": "Feedback or feature records exist, but workspace analytics data is unavailable.",
                }
            )

        # Explicit data-limitation diagnostics
        data_limitations: List[str] = []
        if analytics_summary.total_events == 0:
            data_limitations.append(
                "Product analytics data is unavailable (no telemetry events in the selected window)."
            )
        elif analytics_summary.coverage_state != "complete":
            data_limitations.append(
                f"Product analytics coverage is '{analytics_summary.coverage_state}'; some user/session metrics may be unavailable."
            )
        if prioritization_summary.total_count == 0:
            data_limitations.append(
                "No saved prioritization scenarios exist in this workspace."
            )
        if feedback_summary.total_count == 0:
            data_limitations.append("No customer feedback records exist in this workspace.")
        elif feedback_summary.total_count < 3:
            data_limitations.append(
                f"Customer feedback sample is small ({feedback_summary.total_count} items); recurring patterns may be unreliable."
            )
        if feature_summary.total_count == 0:
            data_limitations.append("No feature intelligence groups exist in this workspace.")

        ws_meta = WorkspaceMetadataContext(
            workspaceId=str(ws_oid),
            name=workspace.name,
            slug=workspace.slug,
            plan=workspace.plan.value if hasattr(workspace.plan, "value") else str(workspace.plan),
            status="archived" if getattr(workspace, "is_archived", False) else "active",
        )

        # Build preliminary metadata and measure serialized context footprint
        limits = {
            "feedback": MAX_FEEDBACK_ITEMS,
            "feature_groups": MAX_FEATURE_GROUPS,
            "pain_points_per_group": MAX_PAIN_POINTS_PER_GROUP,
            "prioritization": MAX_PRIORITIZATION_ITEMS,
            "analytics_features": MAX_ANALYTICS_FEATURES,
            "prds": MAX_PRDS,
            "roadmap_items": MAX_ROADMAP_ITEMS,
        }
        now = datetime.now(timezone.utc)
        context = WorkspaceCopilotContext(
            workspace=ws_meta,
            feedback=feedback_summary,
            featureIntelligence=feature_summary,
            prioritization=prioritization_summary,
            analytics=analytics_summary,
            planning=planning_summary,
            metadata=ContextRetrievalMetadata(
                retrievedAt=now,
                limitsApplied=limits,
                missingDomains=missing_domains,
                partialSignals=partial_signals,
                dataLimitations=data_limitations,
                crossDomainLinks=cross_domain_links,
            ),
        )
        serialized = json.dumps(context.model_dump(by_alias=True, mode="json"), separators=(",", ":"))
        context.metadata.estimated_chars = len(serialized)
        context.metadata.estimated_tokens = math.ceil(len(serialized) / 4)
        return context
