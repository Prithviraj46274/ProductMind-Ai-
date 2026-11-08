"""
ProductMind AI — Feature Group Repository & Persistence Unit Tests
Tests CRUD operations, backward-compatible fields, workspace isolation,
and feedback item linkage on FeatureGroupRepository and FeedbackRepository.
"""

from datetime import datetime, timezone
from bson import ObjectId
import pytest

from app.models.intelligence import FeatureGroup, SentimentDistribution
from app.models.feedback import FeedbackItem
from app.repositories import FeatureGroupRepository, FeedbackRepository
from app.core.enums import FeedbackCategory, FeatureGroupStatus, FeedbackSourceType


@pytest.mark.asyncio
async def test_feature_group_crud_lifecycle(async_db):
    """Verify FeatureGroup creation, retrieval, filtering, and cleanup."""
    fg_repo = FeatureGroupRepository(async_db)
    test_ws_id = ObjectId()

    # 1. Create FeatureGroup
    new_group = FeatureGroup(
        workspace_id=test_ws_id,
        title="Test Automated Reporting Capability",
        category=FeedbackCategory.FEATURE_REQUESTS,
        primary_tag="reporting",
        description="Consolidated intelligence for automated weekly reporting.",
        feature_summary="Automated report generation and distribution.",
        status=FeatureGroupStatus.SUGGESTED,
        sentiment_distribution=SentimentDistribution(Positive=2, Neutral=1, Negative=0),
        pain_points=["Manual report assembly takes 2 hours"],
        feedback_count=3,
        related_feedback_ids=[ObjectId(), ObjectId()],
        common_themes=["reporting", "automation"],
        evidence=["Manual report assembly takes 2 hours"],
        grouping_confidence=0.88,
        grouping_reason="Common reporting automation need.",
        unique_customer_count=2,
    )

    created = await fg_repo.create(new_group)
    try:
        assert created.id is not None
        assert created.title == "Test Automated Reporting Capability"
        assert created.feedback_count == 3
        assert created.unique_customer_count == 2
        assert len(created.related_feedback_ids) == 2

        # 2. Find by workspace and status
        filtered = await fg_repo.find_by_workspace_and_filters(
            workspace_id=test_ws_id,
            status="suggested",
            min_feedback_count=1,
        )
        assert len(filtered) == 1
        assert filtered[0].id == created.id

        # 3. Find by related feedback ID
        matched = await fg_repo.find_by_related_feedback(
            workspace_id=test_ws_id,
            feedback_id=created.related_feedback_ids[0],
        )
        assert matched is not None
        assert matched.id == created.id

        # 4. Workspace isolation: querying with a different workspace ID returns nothing
        diff_ws_id = ObjectId()
        isolated = await fg_repo.find_by_workspace_and_filters(
            workspace_id=diff_ws_id,
            status="suggested",
        )
        assert len(isolated) == 0
    finally:
        # 5. Clean up test document
        await fg_repo.delete(created.id)


@pytest.mark.asyncio
async def test_feedback_item_linkage_to_feature_group(async_db):
    """Verify linking feedback items to a feature group via FeedbackRepository.link_to_feature_group."""
    feedback_repo = FeedbackRepository(async_db)
    test_ws_id = ObjectId()
    test_fg_id = ObjectId()

    # Create temporary feedback item
    item = FeedbackItem(
        workspace_id=test_ws_id,
        title="Need dark mode for late night analysis",
        description="Background is too bright in the evening.",
        source_type=FeedbackSourceType.MANUAL,
    )
    created_item = await feedback_repo.create(item)
    try:
        assert created_item.feature_group_id is None

        # Link to feature group
        modified_count = await feedback_repo.link_to_feature_group(
            feedback_ids=[str(created_item.id)],
            feature_group_id=test_fg_id,
            workspace_id=test_ws_id,
        )
        assert modified_count == 1

        # Verify link
        updated = await feedback_repo.find_by_id(created_item.id)
        assert updated is not None
        assert str(updated.feature_group_id) == str(test_fg_id)
    finally:
        # Clean up test feedback item
        await feedback_repo.delete(created_item.id)
