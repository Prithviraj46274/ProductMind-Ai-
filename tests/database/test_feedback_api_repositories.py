from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
import pytest
from pymongo import ReturnDocument

from app.core.enums import FeedbackCategory
from app.repositories.feedback_repository import FeedbackBatchRepository, FeedbackRepository

WORKSPACE_ID = ObjectId("660011223344556677889902")
BATCH_ID = ObjectId("660011223344556677889904")


@pytest.mark.asyncio
async def test_feedback_page_keeps_workspace_scope_with_filters():
    collection = MagicMock()
    collection.count_documents = AsyncMock(return_value=0)
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    collection.find.return_value = cursor
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = FeedbackRepository(db)

    await repository.find_page(
        WORKSPACE_ID,
        page=2,
        limit=25,
        category=FeedbackCategory.PERFORMANCE,
        linked=False,
        sort="oldest",
    )

    collection.find.assert_called_once_with(
        {
            "workspaceId": WORKSPACE_ID,
            "category": "Performance",
            "$or": [
                {"promotedFeatureId": None},
                {"promotedFeatureId": {"$exists": False}},
            ],
        }
    )
    cursor.skip.assert_called_once_with(25)
    cursor.limit.assert_called_once_with(25)


@pytest.mark.asyncio
async def test_feedback_priority_page_uses_workspace_scoped_pipeline():
    collection = MagicMock()
    collection.count_documents = AsyncMock(return_value=0)
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    collection.aggregate.return_value = cursor
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = FeedbackRepository(db)

    await repository.find_page(
        WORKSPACE_ID,
        page=1,
        limit=10,
        sort="priority",
    )

    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"workspaceId": WORKSPACE_ID}}
    assert pipeline[3] == {"$skip": 0}
    assert pipeline[4] == {"$limit": 10}


@pytest.mark.asyncio
async def test_failed_batch_claim_is_atomic_and_workspace_scoped():
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=None)
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = FeedbackBatchRepository(db)

    result = await repository.claim_failed_batch(BATCH_ID, WORKSPACE_ID)

    assert result is None
    query = collection.find_one_and_update.await_args.args[0]
    assert query == {
        "_id": BATCH_ID,
        "workspaceId": WORKSPACE_ID,
        "status": {"$in": ["partial", "failed"]},
        "rejectedRows": {"$gt": 0},
    }
    assert (
        collection.find_one_and_update.await_args.kwargs["return_document"]
        == ReturnDocument.BEFORE
    )
