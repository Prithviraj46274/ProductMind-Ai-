"""Phase 3.1 unit & API contract tests for analytics batch ingestion and dataset history."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_analytics_batch_repository,
    get_analytics_event_repository,
    get_analytics_rollup_repository,
    get_current_user,
    get_feature_repository,
    get_workspace_membership_repository,
    get_workspace_repository,
)
from app.core.enums import MembershipStatus, PlatformRole, UserRole
from app.main import app
from app.models.analytics import AnalyticsBatch, AnalyticsEvent, AnalyticsIngestedMetrics
from app.models.auth import User, Workspace, WorkspaceMembership

client = TestClient(app)
USER_A_ID = ObjectId("660011223344556677889911")
USER_B_ID = ObjectId("660011223344556677889912")
WS_A_ID = ObjectId("660011223344556677889921")
BATCH_ID = ObjectId("660011223344556677889931")


def _make_user(uid: ObjectId, email: str) -> User:
    return User(
        _id=uid,
        name="Phase3 Test User",
        email=email,
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )


def _make_workspace() -> Workspace:
    return Workspace(
        _id=WS_A_ID,
        name="Phase3 Analytics WS",
        slug="phase3-analytics-ws",
        ownerId=USER_A_ID,
        status="active",
    )


def _make_membership(uid: ObjectId) -> WorkspaceMembership:
    return WorkspaceMembership(
        _id=ObjectId(),
        workspaceId=WS_A_ID,
        userId=uid,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )


def test_events_batch_alias_records_csv_metadata_and_mixed_rows():
    """Verify POST /api/v1/analytics/events/batch stores provenance and reports accepted/duplicate/rejected counts."""
    user_a = _make_user(USER_A_ID, "a@example.com")
    ws_a = _make_workspace()
    mem_a = _make_membership(USER_A_ID)

    created_batches = []
    created_events = {}

    async def fake_create_batch(batch: AnalyticsBatch):
        batch.id = BATCH_ID
        created_batches.append(batch)
        return batch

    async def fake_update_batch(batch_id, fields, workspace_id=None):
        b = created_batches[-1]
        for k, v in fields.items():
            if k == "acceptedRows":
                b.accepted_rows = v
            elif k == "duplicateRows":
                b.duplicate_rows = v
            elif k == "rejectedRows":
                b.rejected_rows = v
            elif k == "status":
                b.status = v
            elif k == "errorSummary":
                b.error_summary = v
        return b

    async def fake_find_event_id(ws_id, event_id):
        return created_events.get(event_id)

    async def fake_create_event(event: AnalyticsEvent):
        event.id = ObjectId()
        created_events[event.event_id] = event
        return event

    async def fake_aggregate_daily(ws_id, date_str):
        return AnalyticsIngestedMetrics(
            totalEvents=len(created_events),
            eventsWithActorId=len(created_events),
            eventsWithSessionId=len(created_events),
            activeUsers=1,
            totalSessions=1,
            topFeature="Analytics Dashboard",
            featureMetrics=[],
            lastEventAt=datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc),
            calculatedAt=datetime.now(timezone.utc),
        )

    app.dependency_overrides[get_current_user] = lambda: user_a
    app.dependency_overrides[get_workspace_repository] = lambda: SimpleNamespace(
        find_by_id=AsyncMock(return_value=ws_a)
    )
    app.dependency_overrides[get_workspace_membership_repository] = lambda: SimpleNamespace(
        find_membership=AsyncMock(return_value=mem_a)
    )
    app.dependency_overrides[get_analytics_batch_repository] = lambda: SimpleNamespace(
        create=AsyncMock(side_effect=fake_create_batch),
        update=AsyncMock(side_effect=fake_update_batch),
    )
    app.dependency_overrides[get_analytics_event_repository] = lambda: SimpleNamespace(
        find_by_event_id=AsyncMock(side_effect=fake_find_event_id),
        create=AsyncMock(side_effect=fake_create_event),
        aggregate_daily_ingested_metrics=AsyncMock(side_effect=fake_aggregate_daily),
    )
    app.dependency_overrides[get_analytics_rollup_repository] = lambda: SimpleNamespace(
        upsert_ingested_metrics=AsyncMock(return_value=None)
    )
    app.dependency_overrides[get_feature_repository] = lambda: SimpleNamespace(
        find_by_workspace_and_id=AsyncMock(return_value=None)
    )

    try:
        resp = client.post(
            f"/api/v1/analytics/events/batch?workspaceId={WS_A_ID}",
            json={
                "fileName": "usage_oct.csv",
                "sourceType": "csv",
                "detectedColumns": ["eventId", "eventName", "eventType", "eventTimestamp"],
                "mappedColumns": {"timestamp": "eventTimestamp", "eventName": "eventName"},
                "items": [
                    {
                        "eventId": "evt-1",
                        "eventName": "Dashboard Viewed",
                        "eventType": "view",
                        "eventTimestamp": "2026-10-15T10:00:00Z",
                        "actorId": "u-1",
                        "sessionId": "s-1",
                        "featureName": "Analytics Dashboard",
                    },
                    {
                        "eventId": "evt-1",
                        "eventName": "Dashboard Viewed",
                        "eventType": "view",
                        "eventTimestamp": "2026-10-15T10:00:00Z",
                        "actorId": "u-1",
                        "sessionId": "s-1",
                        "featureName": "Analytics Dashboard",
                    },
                    {
                        "eventId": "evt-bad",
                        "eventName": "Bad Row",
                        "eventType": "view",
                        "eventTimestamp": "not-a-timestamp",
                    },
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["totalRows"] == 3
        assert body["acceptedRows"] == 1
        assert body["duplicateRows"] == 1
        assert body["rejectedRows"] == 1
        assert body["status"] == "partial"
        assert created_batches[0].file_name == "usage_oct.csv"
        assert created_batches[0].source_type == "csv"
    finally:
        app.dependency_overrides.clear()


def test_list_batches_enforces_workspace_isolation():
    """Verify GET /api/v1/analytics/datasets denies unauthorized users."""
    user_b = _make_user(USER_B_ID, "b@example.com")
    ws_a = _make_workspace()

    app.dependency_overrides[get_current_user] = lambda: user_b
    app.dependency_overrides[get_workspace_repository] = lambda: SimpleNamespace(
        find_by_id=AsyncMock(return_value=ws_a)
    )
    app.dependency_overrides[get_workspace_membership_repository] = lambda: SimpleNamespace(
        find_membership=AsyncMock(return_value=None)
    )
    app.dependency_overrides[get_analytics_batch_repository] = lambda: SimpleNamespace(
        find_by_workspace=AsyncMock(return_value=[])
    )

    try:
        resp = client.get(f"/api/v1/analytics/datasets?workspaceId={WS_A_ID}")
        assert resp.status_code in (403, 404)
    finally:
        app.dependency_overrides.clear()

