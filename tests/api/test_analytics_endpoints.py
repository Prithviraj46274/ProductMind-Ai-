from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

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
from app.models.analytics import (
    AnalyticsBatch,
    AnalyticsDailyRollup,
    AnalyticsEvent,
    AnalyticsIngestedMetrics,
)
from app.models.auth import User, Workspace, WorkspaceMembership

client = TestClient(app)
USER_ID = ObjectId("660011223344556677889901")
WORKSPACE_ID = ObjectId("660011223344556677889902")
BATCH_ID = ObjectId("660011223344556677889903")
ORIGINAL_BATCH_ID = ObjectId("660011223344556677889904")


def _event_payload(**overrides):
    payload = {
        "eventId": "event-1",
        "eventName": "Feature opened",
        "eventType": "view",
        "eventTimestamp": "2024-01-02T03:04:05Z",
        "featureName": "Dashboard",
        "actorId": "user-1",
        "sessionId": "session-1",
        "durationSeconds": 12,
    }
    payload.update(overrides)
    return payload


def _analytics_event(**overrides):
    values = {
        "id": ObjectId("660011223344556677889905"),
        "workspace_id": WORKSPACE_ID,
        "batch_id": ORIGINAL_BATCH_ID,
        "event_id": "event-1",
        "event_name": "Feature opened",
        "event_type": "view",
        "event_timestamp": datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "date": "2024-01-02",
        "feature_name": "Dashboard",
        "actor_id": "user-1",
        "session_id": "session-1",
        "duration_seconds": 12.0,
        "custom_properties": {},
    }
    values.update(overrides)
    return AnalyticsEvent(**values)


def _analytics_batch(**overrides):
    values = {
        "id": BATCH_ID,
        "workspace_id": WORKSPACE_ID,
        "uploaded_by": USER_ID,
        "file_name": "analytics-events.json",
        "source_type": "json",
        "status": "processing",
        "total_rows": 1,
        "started_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return AnalyticsBatch(**values)


def _rollup(date_str="2024-01-02", **overrides):
    metrics = AnalyticsIngestedMetrics(
        totalEvents=3,
        eventsWithActorId=3,
        eventsWithSessionId=3,
        activeUsers=2,
        totalSessions=2,
        durationTotalSeconds=40,
        durationSampleCount=2,
        avgEventDurationSeconds=20,
        lastEventAt=datetime(2024, 1, 2, 12, tzinfo=timezone.utc),
        calculatedAt=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )
    values = {
        "id": ObjectId("660011223344556677889907"),
        "workspace_id": WORKSPACE_ID,
        "date": date_str,
        "ingested_metrics": metrics,
    }
    values.update(overrides)
    return AnalyticsDailyRollup(**values)


@pytest.fixture
def api_state():
    app.dependency_overrides.clear()
    user = User(
        id=USER_ID,
        name="Workspace Owner",
        email="owner@example.test",
        password_hash="mock-password-hash",
        platform_role=PlatformRole.USER,
    )
    workspace = Workspace(
        id=WORKSPACE_ID,
        name="Product Team",
        slug="product-team",
        owner_id=USER_ID,
    )
    workspace_repo = AsyncMock()
    workspace_repo.find_by_id.return_value = workspace
    membership_repo = AsyncMock()
    membership_repo.find_membership.return_value = WorkspaceMembership(
        workspace_id=WORKSPACE_ID,
        user_id=USER_ID,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    events = {}
    batches = {}
    event_repo = AsyncMock()
    batch_repo = AsyncMock()
    rollup_repo = AsyncMock()
    feature_repo = AsyncMock()

    async def find_event(workspace_id, event_id):
        return events.get(event_id)

    async def create_event(event):
        event.id = ObjectId()
        events[event.event_id] = event
        return event

    async def create_batch(batch):
        batch.id = ObjectId()
        batches[batch.id] = batch
        return batch

    async def update_batch(batch_id, updates, workspace_id=None):
        batch = batches.get(batch_id)
        if batch is None or batch.workspace_id != workspace_id:
            return None
        fields = {
            "acceptedRows": "accepted_rows",
            "rejectedRows": "rejected_rows",
            "duplicateRows": "duplicate_rows",
            "errorSummary": "error_summary",
            "completedAt": "completed_at",
        }
        for key, value in updates.items():
            setattr(batch, fields.get(key, key), value)
        return batch

    async def find_batch(batch_id, workspace_id):
        batch = batches.get(ObjectId(batch_id) if isinstance(batch_id, str) else batch_id)
        return batch if batch and batch.workspace_id == workspace_id else None

    async def claim_batch(batch_id, workspace_id):
        batch = await find_batch(batch_id, workspace_id)
        if batch is None or batch.status not in {"partial", "failed"}:
            return None
        claimed = batch.model_copy(deep=True)
        batch.status = "processing"
        return claimed

    event_repo.find_by_event_id.side_effect = find_event
    event_repo.create.side_effect = create_event
    event_repo.aggregate_daily_ingested_metrics.return_value = AnalyticsIngestedMetrics(
        totalEvents=1,
        eventsWithActorId=1,
        eventsWithSessionId=1,
        activeUsers=1,
        totalSessions=1,
        durationTotalSeconds=12,
        durationSampleCount=1,
        avgEventDurationSeconds=12,
        lastEventAt=datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        calculatedAt=datetime.now(timezone.utc),
    )
    event_repo.aggregate_range_overview.return_value = {}
    event_repo.aggregate_feature_page.return_value = {"items": [], "total": 0}
    batch_repo.create.side_effect = create_batch
    batch_repo.update.side_effect = update_batch
    batch_repo.find_by_workspace_and_id.side_effect = find_batch
    batch_repo.claim_failed_batch.side_effect = claim_batch
    rollup_repo.find_ingested_range.return_value = []
    feature_repo.find_by_id.return_value = None

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_workspace_repository] = lambda: workspace_repo
    app.dependency_overrides[get_workspace_membership_repository] = lambda: membership_repo
    app.dependency_overrides[get_analytics_event_repository] = lambda: event_repo
    app.dependency_overrides[get_analytics_batch_repository] = lambda: batch_repo
    app.dependency_overrides[get_analytics_rollup_repository] = lambda: rollup_repo
    app.dependency_overrides[get_feature_repository] = lambda: feature_repo
    yield {
        "workspace_repo": workspace_repo,
        "membership_repo": membership_repo,
        "event_repo": event_repo,
        "batch_repo": batch_repo,
        "rollup_repo": rollup_repo,
        "feature_repo": feature_repo,
        "events": events,
        "batches": batches,
    }
    app.dependency_overrides.clear()


def test_single_event_normalizes_timestamp_to_utc_and_creates_batch(api_state):
    payload = _event_payload(
        eventTimestamp="2024-01-02T00:30:00+02:00",
        date="2024-01-01",
    )

    response = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["date"] == "2024-01-01"
    assert response.json()["eventTimestamp"].startswith("2024-01-01T22:30:00")
    assert response.json()["batchId"] == str(api_state["events"]["event-1"].batch_id)
    assert api_state["event_repo"].create.await_args.args[0].batch_id is not None
    api_state["event_repo"].aggregate_daily_ingested_metrics.assert_awaited_once_with(
        WORKSPACE_ID,
        "2024-01-01",
    )


def test_single_event_rejects_mismatched_utc_date_before_writing(api_state):
    response = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=_event_payload(date="2024-01-03"),
    )

    assert response.status_code == 422
    api_state["batch_repo"].create.assert_not_awaited()
    api_state["event_repo"].create.assert_not_awaited()


def test_single_event_requires_timezone_aware_rfc3339_timestamp(api_state):
    response = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=_event_payload(eventTimestamp="2024-01-02T03:04:05"),
    )

    assert response.status_code == 422
    api_state["batch_repo"].create.assert_not_awaited()


def test_single_event_identical_replay_is_duplicate_and_conflict_is_409(api_state):
    existing = _analytics_event()
    api_state["events"]["event-1"] = existing

    response = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=_event_payload(),
    )

    assert response.status_code == 200
    assert response.json()["batchId"] == str(ORIGINAL_BATCH_ID)
    assert api_state["event_repo"].create.await_count == 0
    assert api_state["batch_repo"].update.await_args.args[1]["duplicateRows"] == 1

    conflicting = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=_event_payload(eventName="A different event"),
    )

    assert conflicting.status_code == 409
    assert api_state["batch_repo"].create.await_count == 1


def test_legacy_sample_event_id_is_not_treated_as_an_ingested_duplicate(api_state):
    api_state["events"]["event-1"] = _analytics_event(batch_id=None)

    response = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=_event_payload(),
    )

    assert response.status_code == 409
    assert api_state["batch_repo"].create.await_count == 0


def test_batch_ingestion_reports_accepted_duplicate_and_rejected_rows(api_state):
    payload = {
        "items": [
            _event_payload(),
            _event_payload(),
            _event_payload(eventId="invalid-date", date="2024-01-03"),
        ]
    }

    response = client.post(
        f"/api/v1/analytics/datasets/upload?workspaceId={WORKSPACE_ID}",
        json=payload,
    )

    assert response.status_code == 201
    result = response.json()
    assert result["totalRows"] == 3
    assert result["acceptedRows"] == 1
    assert result["duplicateRows"] == 1
    assert result["rejectedRows"] == 1
    assert [row["status"] for row in result["results"]] == [
        "accepted",
        "duplicate",
        "rejected",
    ]
    stored_batch = api_state["batches"][ObjectId(result["id"])]
    assert stored_batch.status == "partial"
    assert stored_batch.error_summary[0]["rowNumber"] == 3


def test_batch_rejects_unapproved_custom_properties(api_state):
    response = client.post(
        f"/api/v1/analytics/datasets/upload?workspaceId={WORKSPACE_ID}",
        json={"items": [_event_payload(customProperties={"source": "unknown"})]},
    )

    assert response.status_code == 201
    assert response.json()["rejectedRows"] == 1
    assert api_state["event_repo"].create.await_count == 0


def test_batch_retry_requires_original_row_and_event_id(api_state):
    batch = _analytics_batch(
        status="partial",
        total_rows=2,
        accepted_rows=1,
        rejected_rows=1,
        error_summary=[
            {
                "rowNumber": 2,
                "eventId": "retry-event",
                "errors": [{"field": "eventName", "message": "missing"}],
            }
        ],
    )
    batch.id = BATCH_ID
    api_state["batches"][BATCH_ID] = batch

    response = client.post(
        f"/api/v1/analytics/datasets/{BATCH_ID}/retry?workspaceId={WORKSPACE_ID}",
        json={
            "items": [
                {
                    "rowNumber": 2,
                    "item": _event_payload(eventId="retry-event"),
                }
            ]
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert result["acceptedRows"] == 2
    assert result["rejectedRows"] == 0
    assert api_state["event_repo"].create.await_count == 1


def test_overview_reports_no_data_and_rejects_ranges_over_365_days(api_state):
    no_data = client.get(
        f"/api/v1/analytics/overview?workspaceId={WORKSPACE_ID}&timeRange=7d"
    )
    assert no_data.status_code == 200
    assert no_data.json()["data"]["coverage"]["state"] == "no_data"
    assert no_data.json()["data"]["activeUsers"] is None
    assert no_data.json()["data"]["avgSessionDurationSeconds"] is None
    assert no_data.json()["data"]["accounts"] is None

    too_wide = client.get(
        f"/api/v1/analytics/overview?workspaceId={WORKSPACE_ID}"
        "&startDate=2023-01-01&endDate=2024-01-01"
    )
    assert too_wide.status_code == 422
    api_state["event_repo"].aggregate_range_overview.assert_awaited_once()


def test_overview_marks_raw_events_without_rollups_as_partial(api_state):
    api_state["event_repo"].aggregate_range_overview.return_value = {
        "totalEvents": 1,
        "eventsWithActorId": 1,
        "eventsWithSessionId": 1,
        "activeUsers": 1,
        "totalSessions": 1,
    }

    response = client.get(
        f"/api/v1/analytics/overview?workspaceId={WORKSPACE_ID}&timeRange=7d"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["coverage"]["state"] == "partial"
    assert data["coverage"]["rawEventsAvailable"] == 1


def test_overview_marks_expired_raw_events_partial_and_withholds_distinct_users(api_state):
    api_state["rollup_repo"].find_ingested_range.return_value = [_rollup()]
    api_state["event_repo"].aggregate_range_overview.return_value = {
        "totalEvents": 2,
        "eventsWithActorId": 2,
        "eventsWithSessionId": 2,
        "activeUsers": 2,
        "totalSessions": 2,
    }

    response = client.get(
        f"/api/v1/analytics/overview?workspaceId={WORKSPACE_ID}"
        "&startDate=2024-01-02&endDate=2024-01-02"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["totalEvents"] == 3
    assert data["activeUsers"] is None
    assert data["sessions"] is None
    assert data["avgEventDurationSeconds"] == 20
    assert data["coverage"] == {
        "state": "partial",
        "totalEvents": 3,
        "eventsWithActorId": 3,
        "eventsWithSessionId": 3,
        "rawEventsAvailable": 2,
    }


def test_missing_identifiers_make_range_wide_user_and_session_counts_null(api_state):
    partial_metrics = AnalyticsIngestedMetrics(
        totalEvents=3,
        eventsWithActorId=2,
        eventsWithSessionId=1,
        activeUsers=2,
        totalSessions=1,
        durationTotalSeconds=0,
        durationSampleCount=0,
        lastEventAt=datetime(2024, 1, 2, 12, tzinfo=timezone.utc),
        calculatedAt=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )
    api_state["rollup_repo"].find_ingested_range.return_value = [
        _rollup(ingested_metrics=partial_metrics)
    ]
    api_state["event_repo"].aggregate_range_overview.return_value = {
        "totalEvents": 3,
        "eventsWithActorId": 2,
        "eventsWithSessionId": 1,
        "activeUsers": None,
        "totalSessions": None,
    }

    response = client.get(
        f"/api/v1/analytics/overview?workspaceId={WORKSPACE_ID}"
        "&startDate=2024-01-02&endDate=2024-01-02"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["activeUsers"] is None
    assert data["sessions"] is None
    assert data["coverage"]["state"] == "partial"


def test_usage_trends_use_daily_rollups_without_inventing_session_duration(api_state):
    api_state["rollup_repo"].find_ingested_range.return_value = [_rollup()]
    api_state["event_repo"].aggregate_range_overview.return_value = {
        "totalEvents": 3,
        "eventsWithActorId": 2,
        "eventsWithSessionId": 2,
        "activeUsers": 2,
        "totalSessions": 2,
    }

    response = client.get(
        f"/api/v1/analytics/usage-trends?workspaceId={WORKSPACE_ID}"
        "&startDate=2024-01-02&endDate=2024-01-02"
    )

    assert response.status_code == 200
    point = response.json()["data"]["items"][0]
    assert point["events"] == 3
    assert point["activeUsers"] == 2
    assert point["sessions"] == 2
    assert point["avgEventDurationSeconds"] == 20
    assert "avgSessionDurationSeconds" not in point


def test_funnel_is_explicitly_unavailable_and_date_filtered(api_state):
    response = client.get(
        f"/api/v1/analytics/funnel?workspaceId={WORKSPACE_ID}"
        "&startDate=2024-01-01&endDate=2024-01-02"
    )

    assert response.status_code == 200
    assert response.json()["data"]["available"] is False
    assert api_state["event_repo"].aggregate_range_overview.await_args.args[1] == (
        datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    assert api_state["event_repo"].aggregate_range_overview.await_args.args[2] == (
        datetime(2024, 1, 3, tzinfo=timezone.utc)
    )


def test_feature_adoption_is_measured_from_identifiable_users(api_state):
    api_state["rollup_repo"].find_ingested_range.return_value = [_rollup()]
    api_state["event_repo"].aggregate_range_overview.return_value = {
        "totalEvents": 3,
        "eventsWithActorId": 2,
        "eventsWithSessionId": 2,
        "activeUsers": 2,
        "totalSessions": 2,
    }
    api_state["event_repo"].aggregate_feature_page.return_value = {
        "items": [
            {
                "_id": "Dashboard",
                "eventCount": 2,
                "eventsWithActorId": 2,
                "uniqueUsers": 1,
                "durationTotalSeconds": 10,
                "durationSampleCount": 1,
            }
        ],
        "total": 1,
    }

    response = client.get(
        f"/api/v1/analytics/features?workspaceId={WORKSPACE_ID}"
        "&startDate=2024-01-02&endDate=2024-01-02"
    )

    assert response.status_code == 200
    metric = response.json()["data"]["items"][0]
    assert metric["uniqueUsers"] == 1
    assert metric["adoptionPercent"] == 50
    assert metric["avgEventDurationSeconds"] == 10
    assert metric["durationSampleCount"] == 1


def test_all_time_range_is_capped_and_reported(api_state):
    response = client.get(
        f"/api/v1/analytics/overview?workspaceId={WORKSPACE_ID}&timeRange=all"
    )

    assert response.status_code == 200
    date_range = response.json()["data"]["dateRange"]
    assert date_range["capped"] is True
    assert (datetime.fromisoformat(date_range["endDate"]) - datetime.fromisoformat(
        date_range["startDate"]
    )).days == 364


def test_batch_status_is_workspace_scoped(api_state):
    batch = _analytics_batch(
        status="partial",
        total_rows=2,
        accepted_rows=1,
        rejected_rows=1,
        error_summary=[{"rowNumber": 2, "eventId": "retry-event", "errors": []}],
    )
    batch.id = BATCH_ID
    api_state["batches"][BATCH_ID] = batch

    response = client.get(
        f"/api/v1/analytics/datasets/{BATCH_ID}?workspaceId={WORKSPACE_ID}"
    )

    assert response.status_code == 200
    assert response.json()["duplicateRows"] == 0
    assert response.json()["errorSummary"][0]["rowNumber"] == 2


def test_batch_retry_rejects_unfailed_rows_without_claiming_batch(api_state):
    batch = _analytics_batch(
        status="partial",
        total_rows=2,
        accepted_rows=1,
        rejected_rows=1,
        error_summary=[
            {
                "rowNumber": 2,
                "eventId": "retry-event",
                "errors": [{"field": "eventName", "message": "missing"}],
            }
        ],
    )
    batch.id = BATCH_ID
    api_state["batches"][BATCH_ID] = batch

    response = client.post(
        f"/api/v1/analytics/datasets/{BATCH_ID}/retry?workspaceId={WORKSPACE_ID}",
        json={
            "items": [
                {"rowNumber": 1, "item": _event_payload(eventId="retry-event")}
            ]
        },
    )

    assert response.status_code == 422
    api_state["batch_repo"].claim_failed_batch.assert_not_awaited()


def test_feature_reference_must_match_workspace_feature_name(api_state):
    api_state["feature_repo"].find_by_id.return_value = SimpleNamespace(
        name="Different feature"
    )

    response = client.post(
        f"/api/v1/analytics/events?workspaceId={WORKSPACE_ID}",
        json=_event_payload(
            featureId=str(ObjectId("660011223344556677889906")),
            featureName="Dashboard",
        ),
    )

    assert response.status_code == 422
    api_state["event_repo"].create.assert_not_awaited()
    api_state["batch_repo"].create.assert_not_awaited()
