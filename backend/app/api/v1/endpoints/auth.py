"""
ProductMind AI — Authentication & Session Management Endpoints
Provides registration, login, JWT issuance, refresh token rotation, logout,
and current user profile inspection.
"""

import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    hash_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    ExpiredTokenException,
    InvalidTokenException,
)
from app.models.auth import User, AuthSession
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    TokenRefreshResponse,
    MessageResponse,
)
from app.schemas.user import UserResponse
from app.api.dependencies import (
    get_user_repository,
    get_auth_session_repository,
    get_current_user,
)
from app.repositories.user_repository import UserRepository
from app.repositories.auth_session_repository import AuthSessionRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register New User",
    description="Registers a new user account with secure password hashing. Checks for email uniqueness.",
    response_model=UserResponse,
)
async def register_user(
    payload: RegisterRequest,
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    # 1. Check if email already registered
    existing_user = await user_repo.find_by_email(payload.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    # 2. Hash password securely
    hashed_pw = hash_password(payload.password)

    # 3. Create user domain model
    new_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hashed_pw,
        avatar=payload.avatar,
        theme=payload.theme,
        reduced_motion=payload.reduced_motion,
        is_active=True,
    )

    # 4. Persist to MongoDB
    created_user = await user_repo.create(new_user)

    return UserResponse(
        id=str(created_user.id),
        name=created_user.name,
        email=created_user.email,
        platform_role=created_user.platform_role,
        avatar=created_user.avatar,
        theme=created_user.theme,
        reduced_motion=created_user.reduced_motion,
        is_active=created_user.is_active,
        created_at=created_user.created_at,
        updated_at=created_user.updated_at,
    )


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates credentials, generates an active session record, and issues access & refresh tokens.",
    response_model=TokenResponse,
)
async def login_user(
    request: Request,
    payload: LoginRequest,
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: AuthSessionRepository = Depends(get_auth_session_repository),
) -> TokenResponse:
    # 1. Retrieve user by email
    user = await user_repo.find_by_email(payload.email)

    # 2. Verify existence, active state, and password hash (constant error message to prevent enumeration)
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Update last login timestamp
    await user_repo.update_last_login(user.id)

    # 4. Generate new session family & refresh token
    session_family = str(uuid.uuid4())
    raw_refresh, expire_dt = create_refresh_token(str(user.id), session_family)
    refresh_hash = hash_token(raw_refresh)

    # 5. Extract client metadata
    user_agent = request.headers.get("user-agent", "Unknown Browser")[:300]
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 6. Create AuthSession in database
    auth_session = AuthSession(
        user_id=user.id,
        session_family=session_family,
        token_hash=refresh_hash,
        user_agent=user_agent,
        ip_address=client_ip,
        expires_at=expire_dt,
    )
    saved_session = await session_repo.create(auth_session)

    # 7. Generate short-lived access token
    access_token, expires_in = create_access_token(
        user_id=str(user.id),
        session_id=str(saved_session.id),
        session_family=session_family,
    )

    user_response = UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        platform_role=user.platform_role,
        avatar=user.avatar,
        theme=user.theme,
        reduced_motion=user.reduced_motion,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=expires_in,
        user=user_response,
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Rotate Refresh Token",
    description="Validates a refresh token, verifies against session state, and issues a new access token and rotated refresh token.",
    response_model=TokenRefreshResponse,
)
async def refresh_token(
    payload: RefreshTokenRequest,
    session_repo: AuthSessionRepository = Depends(get_auth_session_repository),
) -> TokenRefreshResponse:
    # 1. Decode refresh token
    try:
        decoded = decode_token(payload.refresh_token)
    except ExpiredTokenException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type for refresh",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decoded.get("sub")
    session_family = decoded.get("session_family")
    if not user_id or not session_family:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    incoming_hash = hash_token(payload.refresh_token)

    # 2. Check for active session in this family
    active_session = await session_repo.find_active_by_family(session_family)

    # 3. Security: Refresh Token Reuse Detection
    # If active session does not exist or token hash doesn't match the current active session token:
    if not active_session or active_session.token_hash != incoming_hash:
        # Revoke all sessions in the family to protect against token theft
        await session_repo.revoke_family(session_family)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or reused refresh token. All sessions revoked for security.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Generate new rotating refresh token
    new_raw_refresh, new_expire_dt = create_refresh_token(user_id, session_family)
    new_token_hash = hash_token(new_raw_refresh)

    # 5. Rotate session token in database
    await session_repo.rotate_session_token(active_session.id, new_token_hash, new_expire_dt)

    # 6. Issue new short-lived access token
    new_access_token, expires_in = create_access_token(
        user_id=user_id,
        session_id=str(active_session.id),
        session_family=session_family,
    )

    return TokenRefreshResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revokes the active session associated with the authenticated user's access token.",
    response_model=MessageResponse,
)
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    session_repo: AuthSessionRepository = Depends(get_auth_session_repository),
) -> MessageResponse:
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        await session_repo.revoke_session(session_id)

    return MessageResponse(
        status="ok",
        message="Successfully logged out. Session has been revoked.",
    )


@router.get(
    "/me",
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Returns the sanitized profile of the currently authenticated user.",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        platform_role=current_user.platform_role,
        avatar=current_user.avatar,
        theme=current_user.theme,
        reduced_motion=current_user.reduced_motion,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.get(
    "/session",
    status_code=status.HTTP_200_OK,
    summary="Verify Active Session",
    description="Endpoint compatible with frontend session verification.",
    response_model=Dict[str, Any],
)
async def get_session(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return {
        "authenticated": True,
        "user": UserResponse(
            id=str(current_user.id),
            name=current_user.name,
            email=current_user.email,
            platform_role=current_user.platform_role,
            avatar=current_user.avatar,
            theme=current_user.theme,
            reduced_motion=current_user.reduced_motion,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        ).model_dump(by_alias=True),
    }

