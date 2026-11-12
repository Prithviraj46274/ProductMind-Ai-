from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
import pytest
from pymongo import ReturnDocument

from app.models.analytics import AnalyticsIngestedMetrics
from app.repositories.analytics_repository import (
    AnalyticsBatchRepository,
    AnalyticsDailyRollupRepository,
    AnalyticsEventRepository,
)

WORKSPACE_ID = ObjectId("660011223344556677889902")
BATCH_ID = ObjectId("660011223344556677889903")


def _mock_database():
    collection = MagicMock()
    database = MagicMock()
    database.__getitem__.return_value = collection
    return collection, database


@pytest.mark.asyncio
async def test_analytics_batch_retry_claim_is_atomic_and_workspace_scoped():
    collection, database = _mock_database()
    collection.find_one_and_update = AsyncMock(return_value=None)
    repository = AnalyticsBatchRepository(database)

    result = await repository.claim_failed_batch(BATCH_ID, WORKSPACE_ID)

    assert result is None
    assert collection.find_one_and_update.await_args.args[0] == {
        "_id": BATCH_ID,
        "workspaceId": WORKSPACE_ID,
        "status": {"$in": ["partial", "failed"]},
        "rejectedRows": {"$gt": 0},
    }
    assert (
        collection.find_one_and_update.await_args.kwargs["return_document"]
        == ReturnDocument.BEFORE
    )


@pytest.mark.asyncio
async def test_daily_ingested_aggregation_is_scoped_and_keeps_missing_ids_null():
    collection, database = _mock_database()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(
        return_value=[
            {
                "totals": [
                    {
                        "totalEvents": 2,
                        "eventsWithActorId": 0,
                        "eventsWithSessionId": 1,
                        "durationTotalSeconds": 30,
                        "durationSampleCount": 1,
                        "lastEventAt": datetime(2024, 1, 2, 12, tzinfo=timezone.utc),
                    }
                ],
                "users": [],
                "sessions": [{"count": 1}],
                "features": [
                    {
                        "_id": "Dashboard",
                        "eventCount": 2,
                        "eventsWithActorId": 0,
                        "uniqueUsers": 0,
                        "durationTotalSeconds": 30,
                        "durationSampleCount": 1,
                    }
                ],
            }
        ]
    )
    collection.aggregate.return_value = cursor
    repository = AnalyticsEventRepository(database)

    metrics = await repository.aggregate_daily_ingested_metrics(
        WORKSPACE_ID,
        "2024-01-02",
    )

    match = collection.aggregate.call_args.args[0][0]["$match"]
    assert match["workspaceId"] == WORKSPACE_ID
    assert match["batchId"] == {"$type": "objectId"}
    assert match["eventTimestamp"] == {
        "$gte": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "$lt": datetime(2024, 1, 3, tzinfo=timezone.utc),
    }
    assert metrics is not None
    assert metrics.total_events == 2
    assert metrics.active_users is None
    assert metrics.total_sessions is None
    assert metrics.avg_event_duration_seconds == 30
    assert metrics.feature_metrics[0].unique_users is None
    assert metrics.feature_metrics[0].avg_event_duration_seconds == 30


@pytest.mark.asyncio
async def test_range_aggregate_filters_workspace_batch_and_inclusive_date_bounds():
    collection, database = _mock_database()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    collection.aggregate.return_value = cursor
    repository = AnalyticsEventRepository(database)
    start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    end = datetime(2024, 3, 1, tzinfo=timezone.utc)

    result = await repository.aggregate_range_overview(
        WORKSPACE_ID,
        start,
        end,
        event_type="view",
        feature_name="Dashboard",
    )

    match = collection.aggregate.call_args.args[0][0]["$match"]
    assert match == {
        "workspaceId": WORKSPACE_ID,
        "batchId": {"$type": "objectId"},
        "eventTimestamp": {"$gte": start, "$lt": end},
        "eventType": "view",
        "featureName": "Dashboard",
    }
    assert result == {}


@pytest.mark.asyncio
async def test_feature_aggregate_scopes_and_bounds_paged_results():
    collection, database = _mock_database()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    collection.aggregate.return_value = cursor
    repository = AnalyticsEventRepository(database)
    start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    end = datetime(2024, 3, 1, tzinfo=timezone.utc)

    await repository.aggregate_feature_page(
        WORKSPACE_ID,
        start,
        end,
        page=2,
        limit=25,
        event_type="view",
    )

    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"] == {
        "workspaceId": WORKSPACE_ID,
        "batchId": {"$type": "objectId"},
        "eventTimestamp": {"$gte": start, "$lt": end},
        "eventType": "view",
    }
    assert pipeline[1] == {
        "$match": {"featureName": {"$type": "string", "$ne": ""}}
    }
    assert pipeline[-1]["$facet"]["items"] == [
        {"$skip": 25},
        {"$limit": 25},
    ]


@pytest.mark.asyncio
async def test_rollup_upsert_changes_only_ingested_metrics_and_timestamps():
    collection, database = _mock_database()
    collection.update_one = AsyncMock()
    repository = AnalyticsDailyRollupRepository(database)
    metrics = AnalyticsIngestedMetrics(
        totalEvents=1,
        eventsWithActorId=1,
        eventsWithSessionId=1,
        activeUsers=1,
        totalSessions=1,
        durationTotalSeconds=10,
        durationSampleCount=1,
        avgEventDurationSeconds=10,
        lastEventAt=datetime(2024, 1, 2, tzinfo=timezone.utc),
        calculatedAt=datetime(2024, 1, 3, tzinfo=timezone.utc),
    )

    await repository.upsert_ingested_metrics(
        WORKSPACE_ID,
        "2024-01-02",
        metrics,
    )

    update = collection.update_one.await_args.args[1]
    assert set(update["$set"]) == {"ingestedMetrics", "updatedAt"}
    assert update["$set"]["ingestedMetrics"]["totalEvents"] == 1
    assert update["$setOnInsert"] == {
        "workspaceId": WORKSPACE_ID,
        "date": "2024-01-02",
        "createdAt": update["$setOnInsert"]["createdAt"],
    }
