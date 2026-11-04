"""
ProductMind AI — Workspace Schemas (Pydantic DTOs)
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import WorkspacePlan, UserRole, MembershipStatus


class WorkspaceSettingsDTO(BaseModel):
    default_theme: str = Field(default="dark", alias="defaultTheme")
    reduced_motion: bool = Field(default=False, alias="reducedMotion")
    allow_guest_viewers: bool = Field(default=True, alias="allowGuestViewers")


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str
    plan: WorkspacePlan = WorkspacePlan.STARTER
    settings: Optional[WorkspaceSettingsDTO] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    plan: Optional[WorkspacePlan] = None
    settings: Optional[WorkspaceSettingsDTO] = None
    is_archived: Optional[bool] = Field(default=None, alias="isArchived")


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    slug: str
    owner_id: str = Field(alias="ownerId")
    plan: WorkspacePlan
    settings: WorkspaceSettingsDTO
    is_archived: bool = Field(alias="isArchived")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

