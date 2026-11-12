"""
ProductMind AI — User & Workspace Membership Repositories
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.database.collections import Collections
from app.models.auth import User, WorkspaceMembership
from app.core.enums import MembershipStatus, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.USERS, User)

    async def find_by_email(self, email: str) -> Optional[User]:
        normalized = email.strip().lower()
        return await self.find_one({"email": normalized})

    async def find_by_legacy_id(self, legacy_id: str) -> Optional[User]:
        return await self.find_one({"legacyId": legacy_id})

    async def update_last_login(self, user_id: Any) -> Optional[User]:
        oid = self._ensure_object_id(user_id)
        return await self.update(oid, {"lastLoginAt": datetime.now(timezone.utc)})

    async def find_public_profiles(self, user_ids: List[Any]) -> Dict[str, Dict[str, Any]]:
        user_oids = [self._ensure_object_id(user_id) for user_id in user_ids]
        if not user_oids:
            return {}
        cursor = self.collection.find(
            {"_id": {"$in": user_oids}, "isActive": True},
            {"name": 1, "avatar": 1},
        )
        return {
            str(doc["_id"]): {"name": doc["name"], "avatar": doc.get("avatar")}
            async for doc in cursor
        }


class WorkspaceMembershipRepository(BaseRepository[WorkspaceMembership]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.WORKSPACE_MEMBERSHIPS, WorkspaceMembership)

    async def find_membership(self, workspace_id: Any, user_id: Any) -> Optional[WorkspaceMembership]:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        return await self.find_one({"workspaceId": ws_oid, "userId": u_oid})

    async def find_user_memberships(self, user_id: Any) -> List[WorkspaceMembership]:
        u_oid = self._ensure_object_id(user_id)
        cursor = self.collection.find(
            {"userId": u_oid, "status": MembershipStatus.ACTIVE.value}
        )
        docs = await cursor.to_list(length=100)
        return [WorkspaceMembership.from_mongo(d) for d in docs]

    async def find_workspace_memberships(
        self,
        workspace_id: Any,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WorkspaceMembership]:
        ws_oid = self._ensure_object_id(workspace_id)
        cursor = (
            self.collection.find({"workspaceId": ws_oid, "status": MembershipStatus.ACTIVE.value})
            .sort("joinedAt", 1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [WorkspaceMembership.from_mongo(doc) for doc in docs]

    async def reactivate_membership(
        self,
        workspace_id: Any,
        user_id: Any,
        role: UserRole,
        invited_by: Any,
    ) -> Optional[WorkspaceMembership]:
        ws_oid = self._ensure_object_id(workspace_id)
        user_oid = self._ensure_object_id(user_id)
        now = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {
                "workspaceId": ws_oid,
                "userId": user_oid,
                "status": MembershipStatus.INACTIVE.value,
            },
            {
                "$set": {
                    "role": role.value,
                    "status": MembershipStatus.ACTIVE.value,
                    "invitedBy": self._ensure_object_id(invited_by),
                    "joinedAt": now,
                    "updatedAt": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return WorkspaceMembership.from_mongo(doc) if doc else None

    async def update_active_role(
        self,
        workspace_id: Any,
        user_id: Any,
        role: UserRole,
    ) -> Optional[WorkspaceMembership]:
        ws_oid = self._ensure_object_id(workspace_id)
        user_oid = self._ensure_object_id(user_id)
        doc = await self.collection.find_one_and_update(
            {
                "workspaceId": ws_oid,
                "userId": user_oid,
                "status": MembershipStatus.ACTIVE.value,
            },
            {
                "$set": {
                    "role": role.value,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return WorkspaceMembership.from_mongo(doc) if doc else None

    async def deactivate_active_member(
        self,
        workspace_id: Any,
        user_id: Any,
    ) -> Optional[WorkspaceMembership]:
        ws_oid = self._ensure_object_id(workspace_id)
        user_oid = self._ensure_object_id(user_id)
        doc = await self.collection.find_one_and_update(
            {
                "workspaceId": ws_oid,
                "userId": user_oid,
                "status": MembershipStatus.ACTIVE.value,
            },
            {
                "$set": {
                    "status": MembershipStatus.INACTIVE.value,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return WorkspaceMembership.from_mongo(doc) if doc else None
