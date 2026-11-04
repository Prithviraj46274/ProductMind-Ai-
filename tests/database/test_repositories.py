"""
ProductMind AI — Repository Operations Tests
Tests CRUD operations, tenant isolation, pagination, sorting, and error handling.
Non-destructive: isolated test records are created and safely cleaned up.
"""

import pytest
from bson import ObjectId
from datetime import datetime

from app.database.collections import Collections
from app.repositories import (
    UserRepository,
    WorkspaceRepository,
    FeedbackRepository,
    FeatureRepository,
    PRDRepository,
    RoadmapRepository,
    ReleaseRepository,
    CopilotConversationRepository,
    CopilotMessageRepository,
    AuditLogRepository,
    DuplicateEntityError,
)
from app.models.planning import Feature
from app.models.feedback import FeedbackItem
from app.models.copilot import CopilotConversation, CopilotMessage
from app.core.enums import FeatureStatus, FeedbackSourceType, CopilotRole


@pytest.mark.asyncio
async def test_user_repository_reads(async_db):
    user_repo = UserRepository(async_db)
    user = await user_repo.find_by_email("alex.rivera@productmind.ai")
    assert user is not None
    assert user.name == "Alex Rivera"

    legacy_user = await user_repo.find_by_legacy_id("usr-1")
    assert legacy_user is not None
    assert legacy_user.id == user.id


@pytest.mark.asyncio
async def test_workspace_repository_reads(async_db):
    ws_repo = WorkspaceRepository(async_db)
    ws = await ws_repo.find_by_slug("apex-saas-product-operations")
    assert ws is not None
    assert ws.plan == "Enterprise Tier"


@pytest.mark.asyncio
async def test_feature_repository_ranked_backlog_and_workspace_isolation(async_db):
    ws_repo = WorkspaceRepository(async_db)
    feat_repo = FeatureRepository(async_db)

    ws = await ws_repo.find_by_slug("apex-saas-product-operations")
    assert ws is not None

    # Verify ranked backlog
    features = await feat_repo.find_ranked_backlog(ws.id, limit=10)
    assert len(features) == 10
    # Verify descending score order
    scores = [f.score for f in features]
    assert scores == sorted(scores, reverse=True)

    # Test strict workspace isolation with a non-existent workspace ID
    isolated_ws_id = ObjectId()
    isolated_features = await feat_repo.find_ranked_backlog(isolated_ws_id)
    assert len(isolated_features) == 0


@pytest.mark.asyncio
async def test_isolated_create_update_delete_cycle(async_db):
    """
    Verifies Create, Read, Update, Delete using an isolated test feature.
    Guarantees no interference with existing data.
    """
    ws_repo = WorkspaceRepository(async_db)
    feat_repo = FeatureRepository(async_db)

    ws = await ws_repo.find_by_slug("apex-saas-product-operations")
    assert ws is not None

    # 1. Create an isolated test record
    test_feature = Feature(
        workspaceId=ws.id,
        name="[TEST] Temporary Isolated Feature Verification",
        description="This is an isolated test document to verify CRUD operations.",
        customerImpact=8.0,
        urgency=7.0,
        demand=9.0,
        businessValue=8.0,
        status=FeatureStatus.BACKLOG,
    )
    created = await feat_repo.create(test_feature)
    assert created.id is not None
    test_id = created.id

    try:
        # 2. Read back
        fetched = await feat_repo.find_by_id(test_id, workspace_id=ws.id)
        assert fetched is not None
        assert fetched.name == "[TEST] Temporary Isolated Feature Verification"

        # 3. Safe Update
        updated = await feat_repo.update(
            test_id,
            {"name": "[TEST] Updated Feature Name", "status": FeatureStatus.EVALUATING.value},
            workspace_id=ws.id,
        )
        assert updated is not None
        assert updated.name == "[TEST] Updated Feature Name"
        assert updated.status == FeatureStatus.EVALUATING

        # 4. Cross-workspace isolation check on update
        fake_ws_id = ObjectId()
        wrong_ws_update = await feat_repo.update(
            test_id,
            {"name": "[TEST] Should Fail"},
            workspace_id=fake_ws_id,
        )
        assert wrong_ws_update is None

    finally:
        # 5. Clean up isolated record
        deleted = await feat_repo.delete(test_id, workspace_id=ws.id)
        assert deleted is True

        # Verify deletion
        gone = await feat_repo.find_by_id(test_id)
        assert gone is None


@pytest.mark.asyncio
async def test_feedback_text_search(async_db):
    ws_repo = WorkspaceRepository(async_db)
    fb_repo = FeedbackRepository(async_db)

    ws = await ws_repo.find_by_slug("apex-saas-product-operations")
    assert ws is not None

    # Search for known text from seed data, e.g. "latency" or "table"
    results = await fb_repo.search_text(ws.id, "latency")
    assert len(results) >= 1
    assert any("latency" in r.title.lower() or "latency" in r.description.lower() for r in results)

