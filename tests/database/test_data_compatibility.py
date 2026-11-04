"""
ProductMind AI — Data Compatibility & Preservation Verification Tests
Validates that existing MongoDB records are 100% compatible with Python models
and that no relationships or data fields are corrupted.
"""

import pytest
from bson import ObjectId

from app.database.collections import Collections
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.feedback import FeedbackItem
from app.models.intelligence import FeatureGroup, CustomerPersona, CompetitorIntel
from app.models.planning import (
    Feature,
    PRD,
    RoadmapItem,
    Release,
    ProductExperiment,
    CustomerJourney,
    PrioritizationScenario,
)
from app.models.analytics import AnalyticsDailyRollup, AnalyticsEvent
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.audit import AuditLog


@pytest.mark.asyncio
async def test_existing_users_compatibility(async_db):
    cursor = async_db[Collections.USERS].find({})
    docs = await cursor.to_list(length=100)
    assert len(docs) >= 1
    for doc in docs:
        user = User.from_mongo(doc)
        assert user.id is not None
        assert user.email is not None
        assert "@" in user.email


@pytest.mark.asyncio
async def test_existing_workspaces_and_memberships(async_db):
    ws_cursor = async_db[Collections.WORKSPACES].find({})
    workspaces = await ws_cursor.to_list(length=100)
    assert len(workspaces) >= 1

    for ws_doc in workspaces:
        ws = Workspace.from_mongo(ws_doc)
        assert ws.id is not None
        assert ws.owner_id is not None

        # Verify owner exists in users collection
        owner = await async_db[Collections.USERS].find_one({"_id": ws.owner_id})
        assert owner is not None, f"Workspace owner {ws.owner_id} not found in users collection!"

        # Verify membership exists for owner
        membership = await async_db[Collections.WORKSPACE_MEMBERSHIPS].find_one(
            {"workspaceId": ws.id, "userId": ws.owner_id}
        )
        assert membership is not None
        mem_obj = WorkspaceMembership.from_mongo(membership)
        assert mem_obj.status == "active"


@pytest.mark.asyncio
async def test_existing_features_and_scoring(async_db):
    cursor = async_db[Collections.FEATURES].find({})
    docs = await cursor.to_list(length=100)
    assert len(docs) == 10

    for doc in docs:
        feat = Feature.from_mongo(doc)
        assert feat.id is not None
        assert feat.workspace_id is not None
        assert 1.0 <= feat.score <= 10.0
        assert feat.priority_tier in ["Critical", "High", "Medium", "Low"]


@pytest.mark.asyncio
async def test_existing_feedback_items(async_db):
    cursor = async_db[Collections.FEEDBACK_ITEMS].find({})
    docs = await cursor.to_list(length=100)
    assert len(docs) == 20

    for doc in docs:
        fb = FeedbackItem.from_mongo(doc)
        assert fb.id is not None
        assert fb.workspace_id is not None
        assert fb.title is not None
        assert fb.description is not None


@pytest.mark.asyncio
async def test_existing_prds_and_releases(async_db):
    prd_cursor = async_db[Collections.PRDS].find({})
    prds = await prd_cursor.to_list(length=100)
    assert len(prds) == 2
    for p in prds:
        prd = PRD.from_mongo(p)
        assert prd.title is not None
        assert prd.sections is not None

    rel_cursor = async_db[Collections.RELEASES].find({})
    releases = await rel_cursor.to_list(length=100)
    assert len(releases) == 2
    for r in releases:
        rel = Release.from_mongo(r)
        assert rel.version is not None
        assert isinstance(rel.readiness_percent, int)


@pytest.mark.asyncio
async def test_existing_analytics_daily_rollups(async_db):
    cursor = async_db[Collections.ANALYTICS_DAILY_ROLLUPS].find({})
    docs = await cursor.to_list(length=100)
    assert len(docs) == 14
    for doc in docs:
        rollup = AnalyticsDailyRollup.from_mongo(doc)
        assert rollup.date is not None
        assert rollup.active_users >= 0
        assert len(rollup.feature_metrics) > 0


@pytest.mark.asyncio
async def test_existing_audit_logs(async_db):
    cursor = async_db[Collections.AUDIT_LOGS].find({})
    docs = await cursor.to_list(length=100)
    assert len(docs) >= 1
    for doc in docs:
        log = AuditLog.from_mongo(doc)
        assert log.actor is not None
        assert log.action is not None

