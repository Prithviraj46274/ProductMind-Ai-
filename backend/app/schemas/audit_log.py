"""
ProductMind AI — Audit Log Schemas (Pydantic DTOs)
"""

from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import AuditEntityType, AuditAction


class AuditLogCreate(BaseModel):
    actor: str = Field(default="System", max_length=120)
    user_id: Optional[str] = Field(default=None, alias="userId")
    entity_type: AuditEntityType = Field(..., alias="entityType")
    entity_id: str = Field(..., alias="entityId")
    action: AuditAction
    description: str = Field(..., max_length=1000)
    previous_state: Optional[Any] = Field(default=None, alias="previousState")
    new_state: Optional[Any] = Field(default=None, alias="newState")


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    actor: str
    user_id: Optional[str] = Field(default=None, alias="userId")
    entity_type: AuditEntityType = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")
    action: AuditAction
    description: str
    previous_state: Optional[Any] = Field(default=None, alias="previousState")
    new_state: Optional[Any] = Field(default=None, alias="newState")
    can_undo: bool = Field(alias="canUndo")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

