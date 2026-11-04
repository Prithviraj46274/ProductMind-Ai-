"""
ProductMind AI — Auth & Workspace Domain Models
Matches Mongoose schemas for User, Workspace, WorkspaceMembership, and AuthSession.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId
from app.core.enums import UserRole, PlatformRole, MembershipStatus, WorkspacePlan


class User(BaseMongoModel):
    name: str = Field(..., min_length=2, max_length=100)
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    email: str = Field(...)
    password_hash: str = Field(..., alias="passwordHash", min_length=8)
    platform_role: PlatformRole = Field(default=PlatformRole.USER, alias="platformRole")
    avatar: Optional[str] = Field(default=None, max_length=300)
    theme: str = Field(default="dark")
    reduced_motion: bool = Field(default=False, alias="reducedMotion")
    is_active: bool = Field(default=True, alias="isActive")
    email_verified_at: Optional[datetime] = Field(default=None, alias="emailVerifiedAt")
    last_login_at: Optional[datetime] = Field(default=None, alias="lastLoginAt")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    default_theme: str = Field(default="dark", alias="defaultTheme")
    reduced_motion: bool = Field(default=False, alias="reducedMotion")
    allow_guest_viewers: bool = Field(default=True, alias="allowGuestViewers")


class Workspace(BaseMongoModel):
    name: str = Field(..., min_length=2, max_length=100)
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    slug: str = Field(...)
    owner_id: PyObjectId = Field(..., alias="ownerId")
    plan: WorkspacePlan = Field(default=WorkspacePlan.STARTER)
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    is_archived: bool = Field(default=False, alias="isArchived")

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, v: str) -> str:
        return v.strip().lower()


class WorkspaceMembership(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    user_id: PyObjectId = Field(..., alias="userId")
    role: UserRole = Field(default=UserRole.PRODUCT_MANAGER)
    status: MembershipStatus = Field(default=MembershipStatus.ACTIVE)
    invited_by: Optional[PyObjectId] = Field(default=None, alias="invitedBy")
    joined_at: Optional[datetime] = Field(default_factory=utc_now, alias="joinedAt")


class AuthSession(BaseMongoModel):
    user_id: PyObjectId = Field(..., alias="userId")
    session_family: str = Field(..., alias="sessionFamily")
    token_hash: str = Field(..., alias="tokenHash")
    user_agent: str = Field(default="Unknown Browser", alias="userAgent", max_length=300)
    ip_address: str = Field(default="127.0.0.1", alias="ipAddress", max_length=45)
    expires_at: datetime = Field(..., alias="expiresAt")
    revoked_at: Optional[datetime] = Field(default=None, alias="revokedAt")
    last_used_at: Optional[datetime] = Field(default_factory=utc_now, alias="lastUsedAt")
