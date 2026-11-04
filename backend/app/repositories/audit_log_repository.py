"""
ProductMind AI — Audit Log Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.audit import AuditLog
from app.core.enums import AuditEntityType, AuditAction
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.AUDIT_LOGS, AuditLog)

    async def find_entity_history(
        self,
        workspace_id: Any,
        entity_type: AuditEntityType,
        entity_id: str,
        limit: int = 50,
    ) -> List[AuditLog]:
        entity_val = entity_type.value if hasattr(entity_type, "value") else entity_type
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"entityType": entity_val, "entityId": str(entity_id)},
            sort=[("createdAt", -1)],
            limit=limit,
        )

    async def find_recent_activity(
        self,
        workspace_id: Any,
        limit: int = 25,
    ) -> List[AuditLog]:
        return await self.find_by_workspace(
            workspace_id,
            sort=[("createdAt", -1)],
            limit=limit,
        )

