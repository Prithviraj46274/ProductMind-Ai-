"""Phase 3.4 tests for Analytics-Driven 6-Factor Prioritization and Before-and-After Verification."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.ai.agents.prioritization import (
    AnalyzePrioritizationRequest,
    PrioritizationAgentOutput,
    PrioritizationService,
)
from app.core.enums import MembershipStatus, PlatformRole, UserRole
from app.models.analytics import (
    AnalyticsDailyRollup,
    AnalyticsIngestedFeatureMetric,
    AnalyticsIngestedMetrics,
    FeatureMetric,
)
from app.models.auth import User, Workspace, WorkspaceMembership


def _mock_agent(fg_id_str: str):
    agent = MagicMock()
    agent.agent_id = "prioritization_agent"
    agent.aevaluate = AsyncMock(
        return_value=SimpleNamespace(
            data=PrioritizationAgentOutput(
                feature_group_id=fg_id_str,
                business_impact_score=80.0,
                business_impact_explanation="Strong enterprise retention value.",
                strategic_alignment_score=75.0,
                strategic_alignment_explanation="Aligns with enterprise security goals.",
                customer_pain_point_severity="High",
                implementation_benefits=["Improves compliance"],
                delay_risks=["Enterprise deal slippage"],
                supporting_evidence=["Need SSO audit trail for SOC2"],
                reasoning="Strong demand and strategic alignment.",
            ),
            metadata=SimpleNamespace(
                provider="groq",
                model="qwen/qwen3.8-27b",
                latency_ms=50.0,
            ),
        )
    )
    return agent


def _mock_group(ws_id: ObjectId, fg_id: ObjectId, title: str = "SSO Audit Trail"):
    grp = MagicMock()
    grp.id = fg_id
    grp.workspace_id = ws_id
    grp.title = title
    grp.description = "Exportable SSO audit trail logs."
    grp.suggested_capability = title
    grp.primary_tag = "sso-audit"
    grp.common_themes = [title, "Audit Logs"]
    grp.feedback_count = 4
    grp.unique_customer_count = 3
    grp.urgency_distribution = {"High": 2, "Medium": 2}
    grp.sentiment_distribution = MagicMock(positive=0, neutral=1, negative=3)
    grp.pain_points = ["Manual audit export"]
    grp.evidence = ["Need SSO audit trail for SOC2"]
    return grp


@pytest.mark.asyncio
async def test_unmatched_feature_marks_usage_impact_unavailable_not_workspace_fallback():
    """Verify unrelated workspace analytics are NOT assigned to an unmatched feature group."""
    ws_id = ObjectId()
    fg_id = ObjectId()
    group = _mock_group(ws_id, fg_id, title="Dark Mode Theme")
    unrelated_rollup = AnalyticsDailyRollup(
        workspaceId=ws_id,
        date="2026-11-11",
        activeUsers=500,
        totalSessions=900,
        totalEvents=2500,
        featureMetrics=[
            FeatureMetric(name="Billing Invoice PDF", eventCount=400, uniqueUsers=200, adoptionPercent=40.0)
        ],
    )

    fg_repo = MagicMock(find_by_workspace=AsyncMock(return_value=[group]))
    rollup_repo = MagicMock(find_by_workspace=AsyncMock(return_value=[unrelated_rollup]))
    p_repo = MagicMock(
        find_by_workspace_and_feature_group=AsyncMock(return_value=None),
        create=AsyncMock(side_effect=lambda doc: setattr(doc, "id", ObjectId()) or doc),
    )

    service = PrioritizationService(
        agent=_mock_agent(str(fg_id)),
        prioritization_repo=p_repo,
        feature_group_repo=fg_repo,
        analytics_rollup_repo=rollup_repo,
    )
    user = MagicMock(id=ObjectId(), platform_role=PlatformRole.PLATFORM_ADMIN)

    res = await service.analyze_prioritization(
        request=AnalyzePrioritizationRequest(workspace_id=str(ws_id), force_reanalyze=True),
        user=user,
    )
    item = res.results[0]
    assert "usage_impact" not in item.factor_scores
    assert "usage_impact" in item.missing_data
    assert item.coverage_percentage == 90.0
    assert item.agent_metadata["usage_analytics_evidence"]["available"] is False


@pytest.mark.asyncio
async def test_before_and_after_usage_data_updates_usage_impact_and_composite_score():
    """Verify Before (no usage data -> 90% coverage) vs After (Atlas rollups -> 100% coverage + 6 factors)."""
    ws_id = ObjectId()
    fg_id = ObjectId()
    group = _mock_group(ws_id, fg_id, title="SSO Audit Trail")

    fg_repo = MagicMock(find_by_workspace=AsyncMock(return_value=[group]))
    rollup_repo = MagicMock(find_by_workspace=AsyncMock(return_value=[]))
    p_repo = MagicMock(
        find_by_workspace_and_feature_group=AsyncMock(return_value=None),
        create=AsyncMock(side_effect=lambda doc: setattr(doc, "id", ObjectId()) or doc),
    )

    service = PrioritizationService(
        agent=_mock_agent(str(fg_id)),
        prioritization_repo=p_repo,
        feature_group_repo=fg_repo,
        analytics_rollup_repo=rollup_repo,
    )
    user = MagicMock(id=ObjectId(), platform_role=PlatformRole.PLATFORM_ADMIN)

    # Test A: Before usage data
    before_res = await service.analyze_prioritization(
        request=AnalyzePrioritizationRequest(workspace_id=str(ws_id), force_reanalyze=True),
        user=user,
    )
    before_item = before_res.results[0]
    assert "usage_impact" not in before_item.factor_scores
    assert before_item.coverage_percentage == 90.0
    assert before_item.missing_data == ["usage_impact"]

    # Test B: After importing multi-day usage rollups for "SSO Audit Trail"
    ts = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    rollup_day_1 = AnalyticsDailyRollup(
        workspaceId=ws_id,
        date="2026-11-10",
        ingestedMetrics=AnalyticsIngestedMetrics(
            totalEvents=50,
            eventsWithActorId=50,
            eventsWithSessionId=50,
            activeUsers=40,
            totalSessions=45,
            featureMetrics=[
                AnalyticsIngestedFeatureMetric(
                    name="SSO Audit Trail",
                    eventCount=50,
                    eventsWithActorId=50,
                    uniqueUsers=40,
                    adoptionPercent=50.0,
                )
            ],
            lastEventAt=ts,
            calculatedAt=ts,
        ),
    )
    rollup_day_2 = AnalyticsDailyRollup(
        workspaceId=ws_id,
        date="2026-11-11",
        ingestedMetrics=AnalyticsIngestedMetrics(
            totalEvents=80,
            eventsWithActorId=80,
            eventsWithSessionId=80,
            activeUsers=100,
            totalSessions=90,
            featureMetrics=[
                AnalyticsIngestedFeatureMetric(
                    name="SSO Audit Trail",
                    eventCount=80,
                    eventsWithActorId=80,
                    uniqueUsers=100,
                    adoptionPercent=75.0,
                )
            ],
            lastEventAt=ts,
            calculatedAt=ts,
        ),
    )
    rollup_repo.find_by_workspace = AsyncMock(return_value=[rollup_day_1, rollup_day_2])

    after_res = await service.analyze_prioritization(
        request=AnalyzePrioritizationRequest(workspace_id=str(ws_id), force_reanalyze=True),
        user=user,
    )
    after_item = after_res.results[0]
    assert "usage_impact" in after_item.factor_scores
    assert after_item.coverage_percentage == 100.0
    assert after_item.missing_data == []
    assert after_item.factor_weights["usage_impact"] == 0.1
    evidence = after_item.agent_metadata["usage_analytics_evidence"]
    assert evidence["available"] is True
    assert evidence["matched_feature"] == "SSO Audit Trail"
    assert evidence["event_count"] == 130
    assert evidence["unique_users"] == 100
    assert evidence["adoption_rate"] == 75.0
    assert evidence["trend_direction"] == "increasing"
    assert after_item.final_score != before_item.final_score


@pytest.mark.asyncio
async def test_prioritization_enforces_workspace_isolation():
    """Verify unauthorized user cannot trigger prioritization on another workspace."""
    ws_id = ObjectId()
    owner_id = ObjectId()
    other_user = User(
        _id=ObjectId(),
        name="Other User",
        email="other@example.com",
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )
    ws = Workspace(_id=ws_id, name="Owner WS", slug="owner-ws", ownerId=owner_id, status="active")
    ws_repo = MagicMock(find_by_id=AsyncMock(return_value=ws))
    mem_repo = MagicMock(find_membership=AsyncMock(return_value=None))

    service = PrioritizationService(
        agent=_mock_agent(str(ObjectId())),
        workspace_repo=ws_repo,
        membership_repo=mem_repo,
    )
    with pytest.raises(HTTPException) as exc:
        await service.analyze_prioritization(
            request=AnalyzePrioritizationRequest(workspace_id=str(ws_id)),
            user=other_user,
        )
    assert exc.value.status_code == 403

