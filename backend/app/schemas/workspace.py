"""
ProductMind AI — Workspace Schemas (Pydantic DTOs)
"""

import re
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from app.core.enums import WorkspacePlan, UserRole, MembershipStatus


class WorkspaceSettingsDTO(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    default_theme: str = Field(default="dark", alias="defaultTheme")
    reduced_motion: bool = Field(default=False, alias="reducedMotion")
    allow_guest_viewers: bool = Field(default=True, alias="allowGuestViewers")


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=3, max_length=63)
    settings: Optional[WorkspaceSettingsDTO] = None

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Slug must be a string")
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("Slug may contain lowercase letters, numbers, and single hyphens")
        return normalized


class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    settings: Optional[WorkspaceSettingsDTO] = None

    @model_validator(mode="after")
    def require_non_null_updates(self) -> "WorkspaceUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one workspace field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Workspace name cannot be null")
        if "settings" in self.model_fields_set and self.settings is None:
            raise ValueError("Workspace settings cannot be null")
        return self


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


class WorkspaceMemberAdd(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    email: str = Field(..., min_length=3, max_length=254)
    role: UserRole = UserRole.PRODUCT_MANAGER

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Email must be a string")
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("A valid email address is required")
        return normalized


class WorkspaceMemberRoleUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    role: UserRole


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    name: str
    avatar: Optional[str] = None
    role: UserRole
    status: MembershipStatus
    joined_at: Optional[datetime] = Field(default=None, alias="joinedAt")
