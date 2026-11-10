"""
ProductMind AI — Analytics Repository
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any, Dict
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.database.collections import Collections
from app.models.analytics import (
    AnalyticsDailyRollup,
    AnalyticsEvent,
    AnalyticsBatch,
    AnalyticsIngestedFeatureMetric,
    AnalyticsIngestedMetrics,
)
from app.repositories.base import BaseRepository


class AnalyticsDailyRollupRepository(BaseRepository[AnalyticsDailyRollup]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ANALYTICS_DAILY_ROLLUPS, AnalyticsDailyRollup)

    async def find_by_date(self, workspace_id: Any, date_str: str) -> Optional[AnalyticsDailyRollup]:
        ws_oid = self._ensure_object_id(workspace_id)
        return await self.find_one({"workspaceId": ws_oid, "date": date_str})

    async def find_date_range(
        self,
        workspace_id: Any,
        start_date: str,
        end_date: str,
    ) -> List[AnalyticsDailyRollup]:
        """Queries daily rollups within partition date range YYYY-MM-DD."""
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"date": {"$gte": start_date, "$lte": end_date}},
            sort=[("date", 1)],
            limit=365,
        )

    async def find_ingested_range(
        self,
        workspace_id: Any,
        start_date: str,
        end_date: str,
    ) -> List[AnalyticsDailyRollup]:
        ws_oid = self._ensure_object_id(workspace_id)
        cursor = (
            self.collection.find(
                {
                    "workspaceId": ws_oid,
                    "date": {"$gte": start_date, "$lte": end_date},
                    "ingestedMetrics": {"$exists": True},
                }
            )
            .sort("date", 1)
            .limit(365)
        )
        docs = await cursor.to_list(length=365)
        return [AnalyticsDailyRollup.from_mongo(doc) for doc in docs]

    async def upsert_ingested_metrics(
        self,
        workspace_id: Any,
        date_str: str,
        metrics: AnalyticsIngestedMetrics,
    ) -> None:
        ws_oid = self._ensure_object_id(workspace_id)
        now = datetime.now(timezone.utc)
        query = {"workspaceId": ws_oid, "date": date_str}
        update = {
            "$set": {
                "ingestedMetrics": metrics.model_dump(by_alias=True),
                "updatedAt": now,
            },
            "$setOnInsert": {
                "workspaceId": ws_oid,
                "date": date_str,
                "createdAt": now,
            },
        }
        try:
            await self.collection.update_one(query, update, upsert=True)
        except DuplicateKeyError:
            await self.collection.update_one(query, update["$set"], upsert=False)


class AnalyticsEventRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ANALYTICS_EVENTS, AnalyticsEvent)

    async def find_recent_events(
        self,
        workspace_id: Any,
        limit: int = 50,
    ) -> List[AnalyticsEvent]:
        return await self.find_by_workspace(
            workspace_id,
            sort=[("eventTimestamp", -1)],
            limit=limit,
        )

    async def find_by_event_id(
        self,
        workspace_id: Any,
        event_id: str,
    ) -> Optional[AnalyticsEvent]:
        ws_oid = self._ensure_object_id(workspace_id)
        doc = await self.collection.find_one(
            {"workspaceId": ws_oid, "eventId": event_id}
        )
        return AnalyticsEvent.from_mongo(doc) if doc else None

    async def aggregate_daily_ingested_metrics(
        self,
        workspace_id: Any,
        date_str: str,
    ) -> Optional[AnalyticsIngestedMetrics]:
        ws_oid = self._ensure_object_id(workspace_id)
        day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        day_end = day_start + timedelta(days=1)
        pipeline = [
            {
                "$match": {
                    "workspaceId": ws_oid,
                    "batchId": {"$type": "objectId"},
                    "eventTimestamp": {"$gte": day_start, "$lt": day_end},
                    "date": date_str,
                }
            },
            {
                "$facet": {
                    "totals": [
                        {
                            "$group": {
                                "_id": None,
                                "totalEvents": {"$sum": 1},
                                "eventsWithActorId": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$ne": ["$actorId", None]},
                                                    {"$ne": ["$actorId", ""]},
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "eventsWithSessionId": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$ne": ["$sessionId", None]},
                                                    {"$ne": ["$sessionId", ""]},
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "durationTotalSeconds": {
                                    "$sum": {"$ifNull": ["$durationSeconds", 0]}
                                },
                                "durationSampleCount": {
                                    "$sum": {
                                        "$cond": [
                                            {"$isNumber": "$durationSeconds"},
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "lastEventAt": {"$max": "$eventTimestamp"},
                            }
                        }
                    ],
                    "users": [
                        {"$match": {"actorId": {"$type": "string", "$ne": ""}}},
                        {"$group": {"_id": "$actorId"}},
                        {"$count": "count"},
                    ],
                    "sessions": [
                        {"$match": {"sessionId": {"$type": "string", "$ne": ""}}},
                        {"$group": {"_id": "$sessionId"}},
                        {"$count": "count"},
                    ],
                    "features": [
                        {"$match": {"featureName": {"$type": "string", "$ne": ""}}},
                        {
                            "$group": {
                                "_id": {
                                    "featureName": "$featureName",
                                    "actorId": "$actorId",
                                },
                                "eventCount": {"$sum": 1},
                                "eventsWithActorId": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$ne": ["$actorId", None]},
                                                    {"$ne": ["$actorId", ""]},
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "durationTotalSeconds": {
                                    "$sum": {"$ifNull": ["$durationSeconds", 0]}
                                },
                                "durationSampleCount": {
                                    "$sum": {
                                        "$cond": [
                                            {"$isNumber": "$durationSeconds"},
                                            1,
                                            0,
                                        ]
                                    }
                                },
                            }
                        },
                        {
                            "$group": {
                                "_id": "$_id.featureName",
                                "eventCount": {"$sum": "$eventCount"},
                                "eventsWithActorId": {
                                    "$sum": "$eventsWithActorId"
                                },
                                "uniqueUsers": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$ne": ["$_id.actorId", None]},
                                                    {"$ne": ["$_id.actorId", ""]},
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "durationTotalSeconds": {
                                    "$sum": "$durationTotalSeconds"
                                },
                                "durationSampleCount": {
                                    "$sum": "$durationSampleCount"
                                },
                            }
                        },
                        {"$sort": {"eventCount": -1, "_id": 1}},
                        {"$limit": 101},
                    ],
                }
            },
        ]
        result = await self.collection.aggregate(
            pipeline,
            allowDiskUse=True,
        ).to_list(length=1)
        if not result or not result[0]["totals"]:
            return None

        totals = result[0]["totals"][0]
        actor_count = totals["eventsWithActorId"]
        session_count = totals["eventsWithSessionId"]
        active_users = (
            result[0]["users"][0]["count"]
            if actor_count == totals["totalEvents"] and result[0]["users"]
            else None
        )
        total_sessions = (
            result[0]["sessions"][0]["count"]
            if session_count == totals["totalEvents"] and result[0]["sessions"]
            else None
        )
        feature_rows = result[0]["features"]
        features_truncated = len(feature_rows) > 100
        feature_metrics = []
        for feature in feature_rows[:100]:
            unique_users = (
                feature["uniqueUsers"]
                if feature["eventsWithActorId"] == feature["eventCount"]
                else None
            )
            adoption = (
                round(unique_users / active_users * 100, 2)
                if unique_users is not None and active_users
                else None
            )
            duration_samples = feature["durationSampleCount"]
            feature_metrics.append(
                AnalyticsIngestedFeatureMetric(
                    name=feature["_id"],
                    eventCount=feature["eventCount"],
                    eventsWithActorId=feature["eventsWithActorId"],
                    uniqueUsers=unique_users,
                    adoptionPercent=adoption,
                    avgEventDurationSeconds=(
                        feature["durationTotalSeconds"] / duration_samples
                        if duration_samples
                        else None
                    ),
                    durationSampleCount=duration_samples,
                )
            )

        duration_samples = totals["durationSampleCount"]
        return AnalyticsIngestedMetrics(
            totalEvents=totals["totalEvents"],
            eventsWithActorId=actor_count,
            eventsWithSessionId=session_count,
            activeUsers=active_users,
            totalSessions=total_sessions,
            durationTotalSeconds=totals["durationTotalSeconds"],
            durationSampleCount=duration_samples,
            avgEventDurationSeconds=(
                totals["durationTotalSeconds"] / duration_samples
                if duration_samples
                else None
            ),
            topFeature=feature_rows[0]["_id"] if feature_rows else None,
            featureMetrics=feature_metrics,
            featuresTruncated=features_truncated,
            lastEventAt=totals["lastEventAt"],
            calculatedAt=datetime.now(timezone.utc),
        )

    async def aggregate_range_overview(
        self,
        workspace_id: Any,
        start: datetime,
        end_exclusive: datetime,
        event_type: Optional[str] = None,
        feature_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws_oid = self._ensure_object_id(workspace_id)
        match: Dict[str, Any] = {
            "workspaceId": ws_oid,
            "batchId": {"$type": "objectId"},
            "eventTimestamp": {"$gte": start, "$lt": end_exclusive},
        }
        if event_type:
            match["eventType"] = event_type
        if feature_name:
            match["featureName"] = feature_name
        pipeline = [
            {"$match": match},
            {
                "$facet": {
                    "totals": [
                        {
                            "$group": {
                                "_id": None,
                                "totalEvents": {"$sum": 1},
                                "eventsWithActorId": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$ne": ["$actorId", None]},
                                                    {"$ne": ["$actorId", ""]},
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "eventsWithSessionId": {
                                    "$sum": {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$ne": ["$sessionId", None]},
                                                    {"$ne": ["$sessionId", ""]},
                                                ]
                                            },
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "durationTotalSeconds": {
                                    "$sum": {"$ifNull": ["$durationSeconds", 0]}
                                },
                                "durationSampleCount": {
                                    "$sum": {
                                        "$cond": [
                                            {"$isNumber": "$durationSeconds"},
                                            1,
                                            0,
                                        ]
                                    }
                                },
                                "lastEventAt": {"$max": "$eventTimestamp"},
                            }
                        }
                    ],
                    "users": [
                        {"$match": {"actorId": {"$type": "string", "$ne": ""}}},
                        {"$group": {"_id": "$actorId"}},
                        {"$count": "count"},
                    ],
                    "sessions": [
                        {"$match": {"sessionId": {"$type": "string", "$ne": ""}}},
                        {"$group": {"_id": "$sessionId"}},
                        {"$count": "count"},
                    ],
                    "days": [
                        {"$group": {"_id": "$date"}},
                        {"$count": "count"},
                    ],
                }
            },
        ]
        results = await self.collection.aggregate(
            pipeline,
            allowDiskUse=True,
        ).to_list(length=1)
        if not results or not results[0]["totals"]:
            return {}
        result = results[0]
        totals = result["totals"][0]
        return {
            **totals,
            "activeUsers": (
                result["users"][0]["count"]
                if totals["eventsWithActorId"] == totals["totalEvents"]
                and result["users"]
                else None
            ),
            "totalSessions": (
                result["sessions"][0]["count"]
                if totals["eventsWithSessionId"] == totals["totalEvents"]
                and result["sessions"]
                else None
            ),
            "observedDays": result["days"][0]["count"] if result["days"] else 0,
        }

    async def aggregate_feature_page(
        self,
        workspace_id: Any,
        start: datetime,
        end_exclusive: datetime,
        *,
        page: int,
        limit: int,
        event_type: Optional[str] = None,
        feature_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        ws_oid = self._ensure_object_id(workspace_id)
        match: Dict[str, Any] = {
            "workspaceId": ws_oid,
            "batchId": {"$type": "objectId"},
            "eventTimestamp": {"$gte": start, "$lt": end_exclusive},
        }
        if event_type:
            match["eventType"] = event_type
        if feature_name:
            match["featureName"] = feature_name
        pipeline = [
            {"$match": match},
            {"$match": {"featureName": {"$type": "string", "$ne": ""}}},
            {
                "$group": {
                    "_id": {
                        "featureName": "$featureName",
                        "actorId": "$actorId",
                    },
                    "eventCount": {"$sum": 1},
                    "eventsWithActorId": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": ["$actorId", None]},
                                        {"$ne": ["$actorId", ""]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "durationTotalSeconds": {
                        "$sum": {"$ifNull": ["$durationSeconds", 0]}
                    },
                    "durationSampleCount": {
                        "$sum": {
                            "$cond": [{"$isNumber": "$durationSeconds"}, 1, 0]
                        }
                    },
                }
            },
            {
                "$group": {
                    "_id": "$_id.featureName",
                    "eventCount": {"$sum": "$eventCount"},
                    "eventsWithActorId": {"$sum": "$eventsWithActorId"},
                    "uniqueUsers": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$ne": ["$_id.actorId", None]},
                                        {"$ne": ["$_id.actorId", ""]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "durationTotalSeconds": {"$sum": "$durationTotalSeconds"},
                    "durationSampleCount": {"$sum": "$durationSampleCount"},
                }
            },
            {"$sort": {"eventCount": -1, "_id": 1}},
            {
                "$facet": {
                    "items": [
                        {"$skip": (page - 1) * limit},
                        {"$limit": limit},
                    ],
                    "total": [{"$count": "count"}],
                }
            },
        ]
        results = await self.collection.aggregate(
            pipeline,
            allowDiskUse=True,
        ).to_list(length=1)
        if not results:
            return {"items": [], "total": 0}
        facet = results[0]
        return {
            "items": facet["items"],
            "total": facet["total"][0]["count"] if facet["total"] else 0,
        }


class AnalyticsBatchRepository(BaseRepository[AnalyticsBatch]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ANALYTICS_BATCHES, AnalyticsBatch)

    async def find_by_workspace_and_id(
        self,
        batch_id: Any,
        workspace_id: Any,
    ) -> Optional[AnalyticsBatch]:
        return await self.find_by_id(batch_id, workspace_id=workspace_id)

    async def claim_failed_batch(
        self,
        batch_id: Any,
        workspace_id: Any,
    ) -> Optional[AnalyticsBatch]:
        batch_oid = self._ensure_object_id(batch_id)
        workspace_oid = self._ensure_object_id(workspace_id)
        doc = await self.collection.find_one_and_update(
            {
                "_id": batch_oid,
                "workspaceId": workspace_oid,
                "status": {"$in": ["partial", "failed"]},
                "rejectedRows": {"$gt": 0},
            },
            {
                "$set": {
                    "status": "processing",
                    "startedAt": datetime.now(timezone.utc),
                    "updatedAt": datetime.now(timezone.utc),
                },
                "$unset": {"completedAt": ""},
            },
            return_document=ReturnDocument.BEFORE,
        )
        return AnalyticsBatch.from_mongo(doc) if doc else None
