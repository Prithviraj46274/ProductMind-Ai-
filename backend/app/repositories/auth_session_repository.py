"""
ProductMind AI — AuthSession Repository
Manages user authentication sessions, token rotation, and family-based revocation.
"""

from datetime import datetime, timezone
from typing import Optional, List, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.auth import AuthSession
from app.repositories.base import BaseRepository


class AuthSessionRepository(BaseRepository[AuthSession]):
    """Repository handling session lifecycle, refresh token hashes, and revocation."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.AUTH_SESSIONS, AuthSession)

    async def find_by_token_hash(self, token_hash: str) -> Optional[AuthSession]:
        """Finds session by hashed refresh token."""
        return await self.find_one({"tokenHash": token_hash})

    async def find_active_by_family(self, session_family: str) -> Optional[AuthSession]:
        """Finds active (unrevoked and unexpired) session within a session family."""
        now = datetime.now(timezone.utc)
        return await self.find_one({
            "sessionFamily": session_family,
            "revokedAt": None,
            "expiresAt": {"$gt": now},
        })

    async def find_by_id_active(self, session_id: Any) -> Optional[AuthSession]:
        """Finds session by _id ensuring it is not revoked or expired."""
        oid = self._ensure_object_id(session_id)
        now = datetime.now(timezone.utc)
        return await self.find_one({
            "_id": oid,
            "revokedAt": None,
            "expiresAt": {"$gt": now},
        })

    async def revoke_session(self, session_id: Any) -> Optional[AuthSession]:
        """Revokes a specific session immediately."""
        oid = self._ensure_object_id(session_id)
        now = datetime.now(timezone.utc)
        return await self.update(oid, {
            "revokedAt": now,
            "lastUsedAt": now,
        })

    async def revoke_family(self, session_family: str) -> int:
        """
        Revokes ALL sessions belonging to a session family.
        Used for token theft/reuse mitigation.
        """
        now = datetime.now(timezone.utc)
        result = await self.collection.update_many(
            {"sessionFamily": session_family, "revokedAt": None},
            {"$set": {"revokedAt": now, "lastUsedAt": now, "updatedAt": now}},
        )
        return result.modified_count

    async def rotate_session_token(
        self,
        session_id: Any,
        new_token_hash: str,
        new_expires_at: datetime,
    ) -> Optional[AuthSession]:
        """Rotates the refresh token hash and updates lastUsedAt for an active session."""
        oid = self._ensure_object_id(session_id)
        now = datetime.now(timezone.utc)
        return await self.update(oid, {
            "tokenHash": new_token_hash,
            "expiresAt": new_expires_at,
            "lastUsedAt": now,
        })

    async def find_user_sessions(self, user_id: Any) -> List[AuthSession]:
        """Retrieves all sessions for a specific user."""
        u_oid = self._ensure_object_id(user_id)
        cursor = self.collection.find({"userId": u_oid}).sort("createdAt", -1)
        docs = await cursor.to_list(length=100)
        return [AuthSession.from_mongo(d) for d in docs]

