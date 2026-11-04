"""
ProductMind AI — Authentication Schemas (Pydantic v2 DTOs)
Defines type-safe request and response contracts for registration, login,
refresh token rotation, and session management.
"""

import re
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.schemas.user import UserResponse

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class RegisterRequest(BaseModel):
    """Payload for new user registration."""
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=2, max_length=100, description="Full user name")
    email: str = Field(..., min_length=5, max_length=254, description="Unique email address")
    password: str = Field(..., min_length=8, max_length=128, description="Secure user password (min 8 chars)")
    avatar: Optional[str] = Field(default=None, max_length=300)
    theme: str = Field(default="dark", max_length=30)
    reduced_motion: bool = Field(default=False, alias="reducedMotion")

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email address format")
        return clean


class LoginRequest(BaseModel):
    """Payload for user login."""
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(..., min_length=5, max_length=254, description="Registered email address")
    password: str = Field(..., min_length=1, max_length=128, description="User password")
    remember_me: bool = Field(default=True, alias="rememberMe")

    @field_validator("email")
    @classmethod
    def validate_and_normalize_email(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email address format")
        return clean


class RefreshTokenRequest(BaseModel):
    """Payload to exchange a refresh token for new access & refresh tokens."""
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(..., alias="refreshToken", min_length=10, description="Active JWT refresh token")


class TokenResponse(BaseModel):
    """Standard authentication response containing tokens and user profile."""
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(..., alias="accessToken", description="Short-lived JWT access token")
    refresh_token: str = Field(..., alias="refreshToken", description="Rotating JWT refresh token")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn", description="Access token expiration window in seconds")
    user: UserResponse = Field(..., description="Sanitized user profile")


class TokenRefreshResponse(BaseModel):
    """Response returned upon successful refresh token rotation."""
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn")


class MessageResponse(BaseModel):
    """Standard informational operation response."""
    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(default="ok")
    message: str = Field(...)
