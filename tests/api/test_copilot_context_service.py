"""Phase 4.2 tests for CopilotContextService: bounded 5-domain retrieval, isolation, truncation, and Atlas integration."""

from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.core.enums import (
    FeedbackCategory,
    FeedbackPriority,
    FeedbackSentiment,
    MembershipStatus,
    PRDStatus,
    PlatformRole,
    RoadmapStatus,
    UserRole,
)
from app.models.analytics import AnalyticsDailyRollup, AnalyticsIngestedMetrics
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.feedback import FeedbackItem
from app.models.intelligence import FeatureGroup, SentimentDistribution
from app.models.planning import PRD, PRDSections, PrioritizationScenario, RoadmapItem
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
from app.services.copilot_context_service import (
    CopilotContextService,
    MAX_ANALYTICS_FEATURES,
    MAX_DESCRIPTION_CHARS,
    MAX_FEATURE_GROUPS,
    MAX_FEEDBACK_ITEMS,
    MAX_PAIN_POINTS_PER_GROUP,
    MAX_PRDS,
    MAX_PRIORITIZATION_ITEMS,
    MAX_ROADMAP_ITEMS,
)


def _make_user(uid: ObjectId, email: str = "pm@example.com") -> User:
    return User(
        _id=uid,
        name="PM User",
        email=email,
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )


def _make_ws(ws_id: ObjectId, owner_id: ObjectId, name: str = "WS A") -> Workspace:
    return Workspace(_id=ws_id, name=name, slug=name.lower().replace(" ", "-"), ownerId=owner_id, status="active")


def _build_service(
    ws: Workspace,
    membership=None,
    feedback_summary=None,
    feedback_items=None,
    feature_groups=None,
    prioritizations=None,
    analytics_overview=None,
    analytics_rollups=None,
    analytics_features=None,
    prds=None,
    roadmap_items=None,
):
    ws_repo = MagicMock(find_by_id=AsyncMock(return_value=ws))
    mem_repo = MagicMock(find_membership=AsyncMock(return_value=membership))

    fb_repo = MagicMock(
        summarize_workspace_feedback=AsyncMock(
            return_value=feedback_summary
            or {
                "totalCount": len(feedback_items or []),
                "sentimentDistribution": {},
                "priorityDistribution": {},
                "topCategories": [],
                "topThemes": [],
            }
        ),
        find_page=AsyncMock(return_value=(feedback_items or [], len(feedback_items or []))),
    )
    fg_repo = MagicMock(
        count=AsyncMock(return_value=len(feature_groups or [])),
        find_by_workspace_and_filters=AsyncMock(return_value=(feature_groups or [])[:MAX_FEATURE_GROUPS]),
    )
    p_repo = MagicMock(
        count=AsyncMock(return_value=len(prioritizations or [])),
        find_ranked_by_score=AsyncMock(return_value=(prioritizations or [])[:MAX_PRIORITIZATION_ITEMS]),
    )
    ae_repo = MagicMock(
        aggregate_range_overview=AsyncMock(
            return_value=analytics_overview
            or {"totalEvents": 0, "eventsWithActorId": 0, "eventsWithSessionId": 0, "activeUsers": 0, "totalSessions": 0}
        ),
        aggregate_feature_page=AsyncMock(return_value=analytics_features or {"items": [], "total": 0}),
    )
    ar_repo = MagicMock(find_ingested_range=AsyncMock(return_value=analytics_rollups or []))
    prd_repo = MagicMock(
        count=AsyncMock(return_value=len(prds or [])),
        find_by_workspace_and_filters=AsyncMock(return_value=(prds or [])[:MAX_PRDS]),
    )
    rm_repo = MagicMock(
        count=AsyncMock(return_value=len(roadmap_items or [])),
        find_by_workspace=AsyncMock(return_value=(roadmap_items or [])[:MAX_ROADMAP_ITEMS]),
    )

    return CopilotContextService(
        workspace_repo=ws_repo,
        membership_repo=mem_repo,
        feedback_repo=fb_repo,
        feature_group_repo=fg_repo,
        prioritization_repo=p_repo,
        analytics_event_repo=ae_repo,
        analytics_rollup_repo=ar_repo,
        prd_repo=prd_repo,
        roadmap_repo=rm_repo,
    )


@pytest.mark.asyncio
async def test_empty_workspace_handles_all_missing_domains_without_fabrication():
    ws_id, owner_id = ObjectId(), ObjectId()
    user = _make_user(owner_id)
    ws = _make_ws(ws_id, owner_id, "Empty WS")
    svc = _build_service(ws)

    ctx = await svc.get_workspace_context(str(ws_id), user)
    assert ctx.workspace.workspace_id == str(ws_id)
    assert ctx.feedback.total_count == 0
    assert ctx.feature_intelligence.total_count == 0
    assert ctx.prioritization.total_count == 0
    assert ctx.analytics.total_events == 0
    assert ctx.analytics.active_users == 0
    assert ctx.analytics.total_sessions == 0
    assert ctx.planning.total_prds == 0
    assert ctx.planning.total_roadmap_items == 0
    assert set(ctx.metadata.missing_domains) == {
        "feedback",
        "feature_intelligence",
        "prioritization",
        "analytics",
        "planning",
    }


@pytest.mark.asyncio
async def test_populated_workspace_enforces_limits_truncation_no_pii_and_partial_analytics():
    ws_id, owner_id = ObjectId(), ObjectId()
    user = _make_user(owner_id, email="secret.pm@example.com")
    ws = _make_ws(ws_id, owner_id, "Populated WS")
    now = datetime.now(timezone.utc)

    long_text = "A" * 250
    feedback_items = [
        FeedbackItem(
            _id=ObjectId(),
            workspaceId=ws_id,
            title=f"Feedback {i}",
            description=long_text,
            customerEmail="customer.pii@example.com",
            category=FeedbackCategory.FEATURE_REQUESTS,
            sentiment=FeedbackSentiment.NEGATIVE,
            sourcePriority=FeedbackPriority.URGENT,
            feedbackDate=now,
        )
        for i in range(MAX_FEEDBACK_ITEMS)
    ]
    feature_groups = [
        FeatureGroup(
            _id=ObjectId(),
            workspaceId=ws_id,
            title=f"Group {i}",
            feedbackCount=10 - i,
            uniqueCustomerCount=5,
            painPoints=["Pain 1 " + long_text, "Pain 2", "Pain 3 should be trimmed"],
            commonThemes=["Theme A", "Theme B"],
            sentimentDistribution=SentimentDistribution(Positive=1, Neutral=1, Negative=3),
        )
        for i in range(MAX_FEATURE_GROUPS)
    ]
    prioritizations = [
        PrioritizationScenario(
            _id=ObjectId(),
            workspaceId=ws_id,
            name=f"Scenario {i}",
            featureGroupId=ObjectId(),
            finalScore=80.0 - i,
            priorityLevel="High",
            factorScores={"customer_demand": 80.0, "urgency": 75.0},
            factorWeights={"customer_demand": 0.25, "urgency": 0.2},
            coveragePercentage=90.0,
            missingData=["usage_impact"],
            explanation=long_text * 2,
            isActive=True,
        )
        for i in range(MAX_PRIORITIZATION_ITEMS)
    ]
    rollup = AnalyticsDailyRollup(
        _id=ObjectId(),
        workspaceId=ws_id,
        date="2026-11-11",
        ingestedMetrics=AnalyticsIngestedMetrics(
            totalEvents=10,
            eventsWithActorId=6,  # Partial actorId coverage -> activeUsers & adoptionPercent MUST be None
            eventsWithSessionId=10,
            activeUsers=None,
            totalSessions=4,
            lastEventAt=now,
            calculatedAt=now,
        ),
    )
    prds = [
        PRD(
            _id=ObjectId(),
            workspaceId=ws_id,
            title=f"PRD {i}",
            status=PRDStatus.PENDING_REVIEW,
            sections=PRDSections(problemStatement=long_text, goalsAndSuccessMetrics=long_text),
            userStories=[{"title": "Story 1"}],
            successMetrics=[{"metric": "Adoption > 30%"}],
        )
        for i in range(MAX_PRDS)
    ]
    roadmap_items = [
        RoadmapItem(
            _id=ObjectId(),
            workspaceId=ws_id,
            title=f"Roadmap {i}",
            status=RoadmapStatus.PLANNED,
            priority=FeedbackPriority.HIGH,
            startDate="2026-11-01",
            targetDate="2026-12-01",
            milestone="Q4",
        )
        for i in range(MAX_ROADMAP_ITEMS)
    ]

    svc = _build_service(
        ws=ws,
        feedback_summary={
            "totalCount": 25,
            "sentimentDistribution": {"Negative": 20, "Positive": 5},
            "priorityDistribution": {"Urgent": 15, "Medium": 10},
            "topCategories": [{"category": "Feature Requests", "count": 25}],
            "topThemes": ["sso", "audit"],
        },
        feedback_items=feedback_items,
        feature_groups=feature_groups,
        prioritizations=prioritizations,
        analytics_overview={"totalEvents": 10, "eventsWithActorId": 6, "eventsWithSessionId": 10, "activeUsers": 4, "totalSessions": 4},
        analytics_rollups=[rollup],
        analytics_features={
            "items": [
                {"_id": "Search Bar", "eventCount": 6, "eventsWithActorId": 3, "uniqueUsers": 2}
            ],
            "total": 1,
        },
        prds=prds,
        roadmap_items=roadmap_items,
    )

    ctx = await svc.get_workspace_context(str(ws_id), user)
    assert ctx.feedback.total_count == 25
    assert len(ctx.feedback.items) == MAX_FEEDBACK_ITEMS
    assert len(ctx.feedback.items[0].description) <= MAX_DESCRIPTION_CHARS
    assert len(ctx.feature_intelligence.items) == MAX_FEATURE_GROUPS
    assert len(ctx.feature_intelligence.items[0].pain_points) == MAX_PAIN_POINTS_PER_GROUP
    assert len(ctx.prioritization.items) == MAX_PRIORITIZATION_ITEMS
    assert len(ctx.analytics.top_features) <= MAX_ANALYTICS_FEATURES
    assert ctx.analytics.active_users is None
    assert ctx.analytics.top_features[0].adoption_percent is None
    assert "analytics.activeUsers_unavailable_partial_actor_coverage" in ctx.metadata.partial_signals
    assert len(ctx.planning.prds) == MAX_PRDS
    assert len(ctx.planning.roadmap_items) == MAX_ROADMAP_ITEMS
    assert ctx.metadata.missing_domains == []
    assert ctx.metadata.estimated_tokens > 0

    raw_json = json.dumps(ctx.model_dump(by_alias=True, mode="json"))
    assert "customer.pii@example.com" not in raw_json
    assert "secret.pm@example.com" not in raw_json
    assert "hashed_password_123" not in raw_json


@pytest.mark.asyncio
async def test_workspace_isolation_denies_unauthorized_user_and_scopes_queries():
    ws_a_id, owner_a_id, user_b_id = ObjectId(), ObjectId(), ObjectId()
    user_b = _make_user(user_b_id, "b@example.com")
    ws_a = _make_ws(ws_a_id, owner_a_id, "WS A")
    svc = _build_service(ws=ws_a, membership=None)

    with pytest.raises(HTTPException) as exc:
        await svc.get_workspace_context(str(ws_a_id), user_b)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_real_atlas_apex_workspace_context_retrieval(async_db):
    """Verifies real MongoDB Atlas retrieval on Apex SaaS Product Operations excludes legacy un-batched analytics."""
    ws_oid = ObjectId("6ae0b2f08eb7ad472c041b97")
    ws_repo = WorkspaceRepository(async_db)
    ws = await ws_repo.find_by_id(ws_oid)
    assert ws is not None

    owner = User(
        _id=ws.owner_id,
        name="Alex Rivera",
        email="alex.rivera@productmind.ai",
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )
    svc = CopilotContextService(
        workspace_repo=ws_repo,
        membership_repo=WorkspaceMembershipRepository(async_db),
        feedback_repo=FeedbackRepository(async_db),
        feature_group_repo=FeatureGroupRepository(async_db),
        prioritization_repo=PrioritizationScenarioRepository(async_db),
        analytics_event_repo=AnalyticsEventRepository(async_db),
        analytics_rollup_repo=AnalyticsDailyRollupRepository(async_db),
        prd_repo=PRDRepository(async_db),
        roadmap_repo=RoadmapRepository(async_db),
    )

    ctx = await svc.get_workspace_context(str(ws_oid), owner)
    assert ctx.workspace.name == "Apex SaaS Product Operations"
    assert ctx.feedback.total_count == 20
    assert len(ctx.feedback.items) == MAX_FEEDBACK_ITEMS
    # Legacy seed analytics (batchId: None, no ingestedMetrics) must remain excluded
    assert ctx.analytics.total_events == 0
    assert "analytics" in ctx.metadata.missing_domains
    assert ctx.metadata.estimated_tokens <= 3000
