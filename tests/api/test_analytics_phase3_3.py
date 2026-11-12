"""Phase 3.3 tests for Feature Analytics, Individual Feature History, Ordered Funnel, and Workspace Isolation."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies import (
    get_analytics_event_repository,
    get_analytics_rollup_repository,
    get_current_user,
    get_workspace_membership_repository,
    get_workspace_repository,
)
from app.core.enums import MembershipStatus, PlatformRole, UserRole
from app.main import app
from app.models.analytics import AnalyticsDailyRollup, AnalyticsIngestedMetrics
from app.models.auth import User, Workspace, WorkspaceMembership
from app.repositories.analytics_repository import AnalyticsEventRepository

client = TestClient(app)
USER_A_ID = ObjectId("660011223344556677889941")
USER_B_ID = ObjectId("660011223344556677889942")
WS_A_ID = ObjectId("660011223344556677889951")


def _user(uid: ObjectId, email: str) -> User:
    return User(
        _id=uid,
        name="Phase33 User",
        email=email,
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )


def _ws() -> Workspace:
    return Workspace(
        _id=WS_A_ID,
        name="Phase33 WS",
        slug="phase33-ws",
        ownerId=USER_A_ID,
        status="active",
    )


def _mem(uid: ObjectId) -> WorkspaceMembership:
    return WorkspaceMembership(
        _id=ObjectId(),
        workspaceId=WS_A_ID,
        userId=uid,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )


def _rollup(total: int = 4, actor: int = 4, sess: int = 4) -> AnalyticsDailyRollup:
    ts = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    return AnalyticsDailyRollup(
        _id=ObjectId(),
        workspaceId=WS_A_ID,
        date="2026-11-10",
        ingestedMetrics=AnalyticsIngestedMetrics(
            totalEvents=total,
            eventsWithActorId=actor,
            eventsWithSessionId=sess,
            activeUsers=2,
            totalSessions=2,
            lastEventAt=ts,
            calculatedAt=ts,
        ),
    )


def test_feature_comparison_and_missing_actor_coverage():
    """Verify includeComparison computes trendDeltaPercent and incomplete actorIds yields None adoption."""
    user_a = _user(USER_A_ID, "p33a@example.com")
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_workspace_repository] = lambda: SimpleNamespace(find_by_id=AsyncMock(return_value=_ws()))
    app.dependency_overrides[get_workspace_membership_repository] = lambda: SimpleNamespace(find_membership=AsyncMock(return_value=_mem(USER_A_ID)))
    app.dependency_overrides[get_analytics_rollup_repository] = lambda: SimpleNamespace(find_ingested_range=AsyncMock(return_value=[_rollup(total=10, actor=10, sess=10)]))
    app.dependency_overrides[get_analytics_event_repository] = lambda: SimpleNamespace(
        aggregate_range_overview=AsyncMock(return_value={"totalEvents": 10, "eventsWithActorId": 10, "eventsWithSessionId": 10, "activeUsers": 4, "totalSessions": 4}),
        aggregate_feature_page=AsyncMock(
            return_value={
                "items": [
                    {"_id": "Search Bar", "eventCount": 6, "eventsWithActorId": 6, "uniqueUsers": 2, "durationTotalSeconds": 120, "durationSampleCount": 4},
                    {"_id": "Export CSV", "eventCount": 4, "eventsWithActorId": 2, "uniqueUsers": 1, "durationTotalSeconds": 0, "durationSampleCount": 0},
                ],
                "total": 2,
            }
        ),
        aggregate_feature_counts=AsyncMock(return_value={"Search Bar": 4, "Export CSV": 8}),
    )

    try:
        resp = client.get(f"/api/v1/analytics/features?workspaceId={WS_A_ID}&startDate=2026-11-01&endDate=2026-11-10&includeComparison=true")
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]["items"]
        assert items[0]["name"] == "Search Bar"
        assert items[0]["adoptionPercent"] == 50.0
        assert items[0]["previousEventCount"] == 4
        assert items[0]["trendDeltaPercent"] == 50.0
        assert items[1]["name"] == "Export CSV"
        assert items[1]["uniqueUsers"] is None
        assert items[1]["adoptionPercent"] is None
        assert items[1]["trendDeltaPercent"] == -50.0
    finally:
        app.dependency_overrides.clear()


def test_usage_trends_feature_history():
    """Verify GET /api/v1/analytics/usage-trends?featureName=... returns daily feature history."""
    user_a = _user(USER_A_ID, "p33a@example.com")
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_workspace_repository] = lambda: SimpleNamespace(find_by_id=AsyncMock(return_value=_ws()))
    app.dependency_overrides[get_workspace_membership_repository] = lambda: SimpleNamespace(find_membership=AsyncMock(return_value=_mem(USER_A_ID)))
    app.dependency_overrides[get_analytics_rollup_repository] = lambda: SimpleNamespace(find_ingested_range=AsyncMock(return_value=[]))
    app.dependency_overrides[get_analytics_event_repository] = lambda: SimpleNamespace(
        aggregate_feature_daily_trends=AsyncMock(
            return_value=[
                {
                    "date": "2026-11-10",
                    "events": 5,
                    "eventsWithActorId": 5,
                    "eventsWithSessionId": 5,
                    "activeUsers": 3,
                    "sessions": 3,
                    "avgEventDurationSeconds": 40.0,
                    "lastEventAt": datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
                }
            ]
        )
    )

    try:
        resp = client.get(f"/api/v1/analytics/usage-trends?workspaceId={WS_A_ID}&timeRange=30d&featureName=Search%20Bar")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["items"][0]["events"] == 5
        assert data["items"][0]["activeUsers"] == 3
    finally:
        app.dependency_overrides.clear()


def test_funnel_ordered_endpoint_and_workspace_isolation():
    """Verify ordered funnel calculation with steps and isolation for unauthorized users."""
    user_a = _user(USER_A_ID, "p33a@example.com")
    user_b = _user(USER_B_ID, "p33b@example.com")
    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_workspace_repository] = lambda: SimpleNamespace(find_by_id=AsyncMock(return_value=_ws()))
    app.dependency_overrides[get_workspace_membership_repository] = lambda: SimpleNamespace(find_membership=AsyncMock(return_value=_mem(USER_A_ID)))
    app.dependency_overrides[get_analytics_rollup_repository] = lambda: SimpleNamespace(find_ingested_range=AsyncMock(return_value=[_rollup(total=6, actor=6, sess=6)]))
    app.dependency_overrides[get_analytics_event_repository] = lambda: SimpleNamespace(
        aggregate_range_overview=AsyncMock(return_value={"totalEvents": 6, "eventsWithActorId": 6, "eventsWithSessionId": 6, "activeUsers": 4, "totalSessions": 4}),
        list_distinct_event_names=AsyncMock(return_value=["view", "click", "complete"]),
        aggregate_ordered_funnel=AsyncMock(
            return_value=[
                {"step": "view", "order": 1, "users": 4, "conversionRate": 100.0, "stepConversionRate": 100.0, "dropOffCount": 0, "dropOffRate": 0.0},
                {"step": "click", "order": 2, "users": 2, "conversionRate": 50.0, "stepConversionRate": 50.0, "dropOffCount": 2, "dropOffRate": 50.0},
                {"step": "complete", "order": 3, "users": 1, "conversionRate": 25.0, "stepConversionRate": 50.0, "dropOffCount": 1, "dropOffRate": 50.0},
            ]
        ),
    )

    try:
        resp = client.get(f"/api/v1/analytics/funnel?workspaceId={WS_A_ID}&timeRange=30d&steps=view,click,complete")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["available"] is True
        assert len(data["steps"]) == 3
        assert data["steps"][1]["dropOffCount"] == 2
        assert data["steps"][2]["conversionRate"] == 25.0

        # Unauthorized user B denied
        app.dependency_overrides[get_current_user] = lambda: user_b
        app.dependency_overrides[get_workspace_membership_repository] = lambda: SimpleNamespace(find_membership=AsyncMock(return_value=None))
        iso = client.get(f"/api/v1/analytics/funnel?workspaceId={WS_A_ID}&timeRange=30d&steps=view,click")
        assert iso.status_code in (403, 404)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_repository_ordered_funnel_enforces_chronological_stage_order():
    """Verify users who perform step 2 BEFORE step 1 are not counted as progressing through step 2."""
    events = [
        {"actorId": "u1", "eventName": "view", "eventType": "view", "eventTimestamp": datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)},
        {"actorId": "u1", "eventName": "complete", "eventType": "complete", "eventTimestamp": datetime(2026, 11, 10, 10, 5, tzinfo=timezone.utc)},
        # u2 completed BEFORE viewing -> should count in view (1), NOT in complete
        {"actorId": "u2", "eventName": "complete", "eventType": "complete", "eventTimestamp": datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)},
        {"actorId": "u2", "eventName": "view", "eventType": "view", "eventTimestamp": datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)},
    ]

    fake_cursor = MagicMock()
    fake_cursor.to_list = AsyncMock(return_value=events)
    fake_col = MagicMock()
    fake_col.aggregate.return_value = fake_cursor
    fake_db = MagicMock()
    fake_db.__getitem__.return_value = fake_col

    repo = AnalyticsEventRepository(fake_db)
    steps = await repo.aggregate_ordered_funnel(
        WS_A_ID,
        datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 11, 0, 0, tzinfo=timezone.utc),
        ["view", "complete"],
    )
    assert steps[0]["users"] == 2
    assert steps[1]["users"] == 1
    assert steps[1]["dropOffCount"] == 1
    assert steps[1]["dropOffRate"] == 50.0
    assert steps[1]["conversionRate"] == 50.0

