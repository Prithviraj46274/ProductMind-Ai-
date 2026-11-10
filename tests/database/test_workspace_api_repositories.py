from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
import pytest
from pymongo import ReturnDocument

from app.core.enums import MembershipStatus, UserRole
from app.repositories.user_repository import UserRepository, WorkspaceMembershipRepository
from app.repositories.workspace_repository import WorkspaceRepository

OWNER_ID = ObjectId("660011223344556677889901")
MEMBER_WORKSPACE_ID = ObjectId("660011223344556677889902")


@pytest.mark.asyncio
async def test_workspace_query_combines_owner_and_active_membership_scope():
    collection = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    collection.find.return_value = cursor
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = WorkspaceRepository(db)

    await repository.find_accessible(
        OWNER_ID,
        [MEMBER_WORKSPACE_ID],
        skip=5,
        limit=10,
    )

    collection.find.assert_called_once_with(
        {
            "isArchived": False,
            "$or": [
                {"ownerId": OWNER_ID},
                {"_id": {"$in": [MEMBER_WORKSPACE_ID]}},
            ],
        }
    )
    cursor.sort.assert_called_once_with("createdAt", -1)
    cursor.skip.assert_called_once_with(5)
    cursor.limit.assert_called_once_with(10)


@pytest.mark.asyncio
async def test_member_reactivation_is_an_atomic_inactive_only_update():
    collection = MagicMock()
    collection.find_one_and_update = AsyncMock(return_value=None)
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = WorkspaceMembershipRepository(db)

    result = await repository.reactivate_membership(
        MEMBER_WORKSPACE_ID,
        OWNER_ID,
        UserRole.PRODUCT_MANAGER,
        OWNER_ID,
    )

    assert result is None
    query = collection.find_one_and_update.await_args.args[0]
    update = collection.find_one_and_update.await_args.args[1]
    assert query == {
        "workspaceId": MEMBER_WORKSPACE_ID,
        "userId": OWNER_ID,
        "status": MembershipStatus.INACTIVE.value,
    }
    assert update["$set"]["status"] == MembershipStatus.ACTIVE.value
    assert update["$set"]["role"] == UserRole.PRODUCT_MANAGER.value
    assert collection.find_one_and_update.await_args.kwargs["return_document"] == ReturnDocument.AFTER


@pytest.mark.asyncio
async def test_public_profile_query_projects_only_name_and_avatar():
    class AsyncCursor:
        def __init__(self, documents):
            self.documents = iter(documents)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.documents)
            except StopIteration:
                raise StopAsyncIteration

    collection = MagicMock()
    collection.find.return_value = AsyncCursor(
        [{"_id": OWNER_ID, "name": "Owner", "avatar": None}]
    )
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = UserRepository(db)

    profiles = await repository.find_public_profiles([OWNER_ID])

    assert profiles == {str(OWNER_ID): {"name": "Owner", "avatar": None}}
    collection.find.assert_called_once_with(
        {"_id": {"$in": [OWNER_ID]}, "isActive": True},
        {"name": 1, "avatar": 1},
    )


@pytest.mark.asyncio
async def test_member_list_filters_active_workspace_members_and_bounds_page():
    collection = MagicMock()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[])
    collection.find.return_value = cursor
    db = MagicMock()
    db.__getitem__.return_value = collection
    repository = WorkspaceMembershipRepository(db)

    await repository.find_workspace_memberships(
        MEMBER_WORKSPACE_ID,
        skip=20,
        limit=25,
    )

    collection.find.assert_called_once_with(
        {
            "workspaceId": MEMBER_WORKSPACE_ID,
            "status": MembershipStatus.ACTIVE.value,
        }
    )
    cursor.sort.assert_called_once_with("joinedAt", 1)
    cursor.skip.assert_called_once_with(20)
    cursor.limit.assert_called_once_with(25)
