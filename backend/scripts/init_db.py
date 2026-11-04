"""
ProductMind AI — Database Index Management & Initialization Script
Replaces server/src/scripts/init-db.js.

Connects to MongoDB, validates index specifications across all 23 collections,
compares index state against live collections, and builds missing indexes safely.
Does not drop any collections or existing indexes.
"""

import argparse
import sys
from typing import Dict, List, Tuple
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel, MongoClient
from pymongo.errors import PyMongoError

# Add parent directory to path for imports
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.database.collections import Collections


def get_index_specifications() -> Dict[str, List[IndexModel]]:
    """Returns canonical index specifications for all 23 collections."""
    specs: Dict[str, List[IndexModel]] = {}

    # 1. users
    specs[Collections.USERS] = [
        IndexModel([("email", ASCENDING)], unique=True, name="email_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("isActive", ASCENDING)], name="isActive_1"),
    ]

    # 2. workspaces
    specs[Collections.WORKSPACES] = [
        IndexModel([("slug", ASCENDING)], unique=True, name="slug_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("ownerId", ASCENDING)], name="ownerId_1"),
        IndexModel([("isArchived", ASCENDING)], name="isArchived_1"),
    ]

    # 3. workspace_memberships
    specs[Collections.WORKSPACE_MEMBERSHIPS] = [
        IndexModel([("workspaceId", ASCENDING), ("userId", ASCENDING)], unique=True, name="workspaceId_1_userId_1"),
        IndexModel([("userId", ASCENDING), ("status", ASCENDING)], name="userId_1_status_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("userId", ASCENDING)], name="userId_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
    ]

    # 4. auth_sessions
    specs[Collections.AUTH_SESSIONS] = [
        IndexModel([("tokenHash", ASCENDING)], unique=True, name="tokenHash_1"),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0, name="expiresAt_1"),
        IndexModel([("userId", ASCENDING)], name="userId_1"),
        IndexModel([("sessionFamily", ASCENDING)], name="sessionFamily_1"),
        IndexModel([("revokedAt", ASCENDING)], name="revokedAt_1"),
    ]

    # 5. feedback_batches
    specs[Collections.FEEDBACK_BATCHES] = [
        IndexModel([("workspaceId", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("fileHash", ASCENDING)], name="fileHash_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
    ]

    # 6. feedback_items
    specs[Collections.FEEDBACK_ITEMS] = [
        IndexModel([("workspaceId", ASCENDING), ("feedbackDate", DESCENDING)], name="workspaceId_1_feedbackDate_-1"),
        IndexModel(
            [("workspaceId", ASCENDING), ("category", ASCENDING), ("sentiment", ASCENDING), ("sourcePriority", ASCENDING)],
            name="workspaceId_1_category_1_sentiment_1_sourcePriority_1",
        ),
        IndexModel(
            [("workspaceId", ASCENDING), ("sourceType", ASCENDING), ("externalId", ASCENDING)],
            unique=True,
            partialFilterExpression={"externalId": {"$type": "string"}},
            name="workspaceId_1_sourceType_1_externalId_1",
        ),
        IndexModel([("title", TEXT), ("description", TEXT)], name="title_text_description_text"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("category", ASCENDING)], name="category_1"),
        IndexModel([("sentiment", ASCENDING)], name="sentiment_1"),
        IndexModel([("sourcePriority", ASCENDING)], name="sourcePriority_1"),
        IndexModel([("feedbackDate", ASCENDING)], name="feedbackDate_1"),
        IndexModel([("featureGroupId", ASCENDING)], name="featureGroupId_1"),
        IndexModel([("promotedFeatureId", ASCENDING)], name="promotedFeatureId_1"),
        IndexModel([("processingStatus", ASCENDING)], name="processingStatus_1"),
    ]

    # 7. analytics_batches
    specs[Collections.ANALYTICS_BATCHES] = [
        IndexModel([("workspaceId", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("fileHash", ASCENDING)], name="fileHash_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
    ]

    # 8. analytics_events
    specs[Collections.ANALYTICS_EVENTS] = [
        IndexModel([("workspaceId", ASCENDING), ("eventTimestamp", DESCENDING)], name="workspaceId_1_eventTimestamp_-1"),
        IndexModel([("workspaceId", ASCENDING), ("featureName", ASCENDING), ("date", DESCENDING)], name="workspaceId_1_featureName_1_date_-1"),
        IndexModel([("workspaceId", ASCENDING), ("eventId", ASCENDING)], unique=True, name="workspaceId_1_eventId_1"),
        IndexModel([("eventTimestamp", ASCENDING)], expireAfterSeconds=7776000, name="eventTimestamp_1"),  # 90 days
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("batchId", ASCENDING)], name="batchId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("eventType", ASCENDING)], name="eventType_1"),
        IndexModel([("date", ASCENDING)], name="date_1"),
        IndexModel([("actorId", ASCENDING)], name="actorId_1"),
        IndexModel([("sessionId", ASCENDING)], name="sessionId_1"),
        IndexModel([("featureName", ASCENDING)], name="featureName_1"),
    ]

    # 9. analytics_daily_rollups
    specs[Collections.ANALYTICS_DAILY_ROLLUPS] = [
        IndexModel([("workspaceId", ASCENDING), ("date", ASCENDING)], unique=True, name="workspaceId_1_date_1"),
        IndexModel([("workspaceId", ASCENDING), ("date", DESCENDING)], name="workspaceId_1_date_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("date", ASCENDING)], name="date_1"),
    ]

    # 10. feature_groups
    specs[Collections.FEATURE_GROUPS] = [
        IndexModel([("workspaceId", ASCENDING), ("feedbackCount", DESCENDING)], name="workspaceId_1_feedbackCount_-1"),
        IndexModel([("workspaceId", ASCENDING), ("status", ASCENDING), ("category", ASCENDING)], name="workspaceId_1_status_1_category_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("category", ASCENDING)], name="category_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("promotedFeatureId", ASCENDING)], name="promotedFeatureId_1"),
    ]

    # 11. customer_personas
    specs[Collections.CUSTOMER_PERSONAS] = [
        IndexModel([("workspaceId", ASCENDING), ("isFavorite", DESCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_isFavorite_-1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("isFavorite", ASCENDING)], name="isFavorite_1"),
    ]

    # 12. competitor_intel
    specs[Collections.COMPETITOR_INTEL] = [
        IndexModel([("workspaceId", ASCENDING), ("name", ASCENDING)], name="workspaceId_1_name_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
    ]

    # 13. features
    specs[Collections.FEATURES] = [
        IndexModel([("workspaceId", ASCENDING), ("score", DESCENDING)], name="workspaceId_1_score_-1"),
        IndexModel([("workspaceId", ASCENDING), ("status", ASCENDING), ("priorityTier", ASCENDING)], name="workspaceId_1_status_1_priorityTier_1"),
        IndexModel([("workspaceId", ASCENDING), ("targetRelease", ASCENDING), ("status", ASCENDING)], name="workspaceId_1_targetRelease_1_status_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
        IndexModel([("priorityTier", ASCENDING)], name="priorityTier_1"),
        IndexModel([("score", ASCENDING)], name="score_1"),
        IndexModel([("featureGroupId", ASCENDING)], name="featureGroupId_1"),
    ]

    # 14. prioritization_scenarios
    specs[Collections.PRIORITIZATION_SCENARIOS] = [
        IndexModel([("workspaceId", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
    ]

    # 15. prds
    specs[Collections.PRDS] = [
        IndexModel([("workspaceId", ASCENDING), ("featureId", ASCENDING)], name="workspaceId_1_featureId_1"),
        IndexModel([("workspaceId", ASCENDING), ("updatedAt", DESCENDING)], name="workspaceId_1_updatedAt_-1"),
        IndexModel([("workspaceId", ASCENDING), ("status", ASCENDING)], name="workspaceId_1_status_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("featureId", ASCENDING)], name="featureId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
    ]

    # 16. roadmap_items
    specs[Collections.ROADMAP_ITEMS] = [
        IndexModel([("workspaceId", ASCENDING), ("milestone", ASCENDING), ("targetDate", ASCENDING)], name="workspaceId_1_milestone_1_targetDate_1"),
        IndexModel([("workspaceId", ASCENDING), ("status", ASCENDING)], name="workspaceId_1_status_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("featureId", ASCENDING)], name="featureId_1"),
        IndexModel([("releaseId", ASCENDING)], name="releaseId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
        IndexModel([("targetDate", ASCENDING)], name="targetDate_1"),
        IndexModel([("milestone", ASCENDING)], name="milestone_1"),
    ]

    # 17. releases
    specs[Collections.RELEASES] = [
        IndexModel([("workspaceId", ASCENDING), ("version", ASCENDING)], unique=True, name="workspaceId_1_version_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("plannedDate", ASCENDING)], name="plannedDate_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
    ]

    # 18. product_experiments
    specs[Collections.PRODUCT_EXPERIMENTS] = [
        IndexModel([("workspaceId", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_status_1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
        IndexModel([("linkedFeatureId", ASCENDING)], name="linkedFeatureId_1"),
        IndexModel([("status", ASCENDING)], name="status_1"),
    ]

    # 19. customer_journeys
    specs[Collections.CUSTOMER_JOURNEYS] = [
        IndexModel([("workspaceId", ASCENDING), ("order", ASCENDING)], unique=True, name="workspaceId_1_order_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
    ]

    # 20. copilot_conversations
    specs[Collections.COPILOT_CONVERSATIONS] = [
        IndexModel([("workspaceId", ASCENDING), ("userId", ASCENDING), ("lastMessageAt", DESCENDING)], name="workspaceId_1_userId_1_lastMessageAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("userId", ASCENDING)], name="userId_1"),
        IndexModel([("isArchived", ASCENDING)], name="isArchived_1"),
        IndexModel([("lastMessageAt", ASCENDING)], name="lastMessageAt_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
    ]

    # 21. copilot_messages
    specs[Collections.COPILOT_MESSAGES] = [
        IndexModel([("conversationId", ASCENDING), ("createdAt", ASCENDING)], name="conversationId_1_createdAt_1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("conversationId", ASCENDING)], name="conversationId_1"),
        IndexModel([("legacyId", ASCENDING)], name="legacyId_1"),
    ]

    # 22. saved_reports
    specs[Collections.SAVED_REPORTS] = [
        IndexModel([("workspaceId", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("reportType", ASCENDING)], name="reportType_1"),
    ]

    # 23. audit_logs
    specs[Collections.AUDIT_LOGS] = [
        IndexModel([("workspaceId", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_createdAt_-1"),
        IndexModel([("workspaceId", ASCENDING), ("entityType", ASCENDING), ("entityId", ASCENDING), ("createdAt", DESCENDING)], name="workspaceId_1_entityType_1_entityId_1_createdAt_-1"),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=15552000, name="expiresAt_1"),  # 180 days
        IndexModel([("workspaceId", ASCENDING)], name="workspaceId_1"),
        IndexModel([("entityType", ASCENDING)], name="entityType_1"),
        IndexModel([("entityId", ASCENDING)], name="entityId_1"),
        IndexModel([("action", ASCENDING)], name="action_1"),
        IndexModel([("canUndo", ASCENDING)], name="canUndo_1"),
    ]

    return specs


def compare_indexes(db, specs: Dict[str, List[IndexModel]]) -> Dict[str, Dict]:
    """Compares planned index specifications against existing indexes in MongoDB."""
    comparison = {}
    for col_name, planned_models in specs.items():
        existing_info = list(db[col_name].list_indexes()) if col_name in db.list_collection_names() else []
        existing_names = {idx["name"] for idx in existing_info}
        
        planned_names = {model.document.get("name") for model in planned_models}
        
        missing = planned_names - existing_names
        extra = existing_names - planned_names - {"_id_"}  # ignore default _id_
        
        comparison[col_name] = {
            "existing_count": len(existing_info),
            "planned_count": len(planned_models) + 1,  # include _id_
            "missing_indexes": list(missing),
            "extra_indexes": list(extra),
            "in_sync": len(missing) == 0,
        }
    return comparison


def init_indexes(uri: str = None, db_name: str = None, check_only: bool = False) -> bool:
    """Synchronizes indexes for all 23 collections."""
    mongo_uri = uri or settings.MONGODB_URI
    target_db = db_name or settings.DATABASE_NAME

    print("=" * 70)
    print("ProductMind AI - Python Database Index Initialization")
    print(f"Target Database: {target_db}")
    print("=" * 70)

    client = MongoClient(mongo_uri)
    db = client[target_db]
    specs = get_index_specifications()

    comparison = compare_indexes(db, specs)
    all_in_sync = True

    print(f"\nAnalyzing indexes across {len(specs)} collections...\n")
    print(f"{'Collection Name':<28} | {'Existing':<8} | {'Planned':<8} | {'Status'}")
    print("-" * 70)

    for col_name, status in sorted(comparison.items()):
        status_str = "IN SYNC" if status["in_sync"] else f"MISSING {len(status['missing_indexes'])}"
        if not status["in_sync"]:
            all_in_sync = False
        print(f"{col_name:<28} | {status['existing_count']:<8} | {status['planned_count']:<8} | {status_str}")

    if check_only:
        print("\n[Check Mode] Completed. No index modifications were performed.")
        client.close()
        return all_in_sync

    print("\nSynchronizing missing indexes safely (no drops)...")
    created_count = 0
    for col_name, planned_models in specs.items():
        missing_names = set(comparison[col_name]["missing_indexes"])
        if missing_names:
            models_to_create = [m for m in planned_models if m.document.get("name") in missing_names]
            try:
                db[col_name].create_indexes(models_to_create)
                print(f"  + Created {len(models_to_create)} indexes for {col_name}")
                created_count += len(models_to_create)
            except PyMongoError as err:
                print(f"  ! Error creating indexes on {col_name}: {err}")

    print(f"\n[Result] Index synchronization complete. {created_count} missing indexes created.")
    client.close()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize and verify ProductMind AI MongoDB indexes.")
    parser.add_argument("--check", action="store_true", help="Compare and verify indexes without applying changes.")
    parser.add_argument("--db-name", type=str, default=None, help="Target database name override.")
    parser.add_argument("--uri", type=str, default=None, help="MongoDB connection URI override.")
    args = parser.parse_args()

    success = init_indexes(uri=args.uri, db_name=args.db_name, check_only=args.check)
    sys.exit(0 if success else 1)
