"""
ProductMind AI — User Schemas (Pydantic DTOs)
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from app.core.enums import PlatformRole, UserRole


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str
    password: str = Field(..., min_length=8)
    platform_role: PlatformRole = Field(default=PlatformRole.USER, alias="platformRole")
    avatar: Optional[str] = None
    theme: str = "dark"
    reduced_motion: bool = Field(default=False, alias="reducedMotion")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    avatar: Optional[str] = None
    theme: Optional[str] = None
    reduced_motion: Optional[bool] = Field(default=None, alias="reducedMotion")
    is_active: Optional[bool] = Field(default=None, alias="isActive")


class UserResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    name: str
    email: str
    platform_role: PlatformRole = Field(alias="platformRole")
    avatar: Optional[str] = None
    theme: str
    reduced_motion: bool = Field(alias="reducedMotion")
    is_active: bool = Field(alias="isActive")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

