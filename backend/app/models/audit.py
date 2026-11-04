"""
ProductMind AI — Audit Log Domain Model
Matches Mongoose schema for AuditLog, supporting activity tracing and state diffs.
"""

from datetime import datetime, timedelta
from typing import Optional, Any
from pydantic import Field, model_validator
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId
from app.core.enums import AuditEntityType, AuditAction


class AuditLog(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    actor: str = Field(default="System", max_length=120)
    user_id: Optional[PyObjectId] = Field(default=None, alias="userId")
    entity_type: AuditEntityType = Field(..., alias="entityType")
    entity_id: str = Field(..., alias="entityId")
    action: AuditAction = Field(...)
    description: str = Field(..., max_length=1000)
    previous_state: Optional[Any] = Field(default=None, alias="previousState")
    new_state: Optional[Any] = Field(default=None, alias="newState")
    can_undo: bool = Field(default=False, alias="canUndo")
    expires_at: Optional[datetime] = Field(default=None, alias="expiresAt")

    @model_validator(mode="after")
    def compute_defaults(self) -> "AuditLog":
        if self.expires_at is None:
            object.__setattr__(self, "expires_at", utc_now() + timedelta(days=180))
        # Determine undo eligibility
        reversible = [AuditAction.CREATED, AuditAction.UPDATED, AuditAction.DELETED]
        if self.action in reversible and (self.action == AuditAction.CREATED or self.previous_state is not None):
            object.__setattr__(self, "can_undo", True)
        return self
