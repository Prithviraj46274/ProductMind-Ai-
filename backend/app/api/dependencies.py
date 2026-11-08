"""
ProductMind AI — FastAPI Dependency Injection Layer
Provides reusable, non-duplicating dependencies for MongoDB clients, databases,
collection registries, domain repositories, and user authentication.
"""

from typing import Type, Optional, Union
from fastapi import Request, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.security import decode_token, ExpiredTokenException, InvalidTokenException
from app.database.collections import Collections
from app.database.connection import MongoDBManager
from app.models.auth import User
from app.repositories import (
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
    AuthSessionRepository,
    FeedbackRepository,
    FeedbackBatchRepository,
    FeatureRepository,
    AnalyticsDailyRollupRepository,
    AnalyticsEventRepository,
    AnalyticsBatchRepository,
    PRDRepository,
    RoadmapRepository,
    ReleaseRepository,
    CopilotConversationRepository,
    CopilotMessageRepository,
    AuditLogRepository,
    FeatureGroupRepository,
    CustomerPersonaRepository,
    CompetitorIntelRepository,
    ProductExperimentRepository,
    CustomerJourneyRepository,
    PrioritizationScenarioRepository,
    SavedReportRepository,
)

# HTTP Bearer security scheme for Swagger UI & OpenAPI documentation
http_bearer = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    scheme_name="BearerAuth",
    description="Enter your JWT access token",
)
# Backward-compatibility alias
oauth2_scheme = http_bearer


# -------------------------------------------------------------------------
# Core Database Engine Dependencies
# -------------------------------------------------------------------------

async def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    """
    Retrieves the active AsyncIOMotorClient from FastAPI application state.
    Avoids reconnecting on individual API requests.
    """
    client: AsyncIOMotorClient = getattr(request.app.state, "mongo_client", None)
    if client is None:
        client = MongoDBManager._async_client
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable: client not initialized",
        )
    return client


async def get_mongo_db(request: Request) -> AsyncIOMotorDatabase:
    """
    Retrieves the active AsyncIOMotorDatabase from FastAPI application state.
    """
    db: AsyncIOMotorDatabase = getattr(request.app.state, "mongo_db", None)
    if db is None:
        db = MongoDBManager._async_db
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable: database not connected",
        )
    return db


def get_collections() -> Type[Collections]:
    """Provides the authoritative collection name registry."""
    return Collections


# -------------------------------------------------------------------------
# Domain Repositories Dependencies
# -------------------------------------------------------------------------

def get_user_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> UserRepository:
    return UserRepository(db)


def get_auth_session_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AuthSessionRepository:
    return AuthSessionRepository(db)


def get_workspace_membership_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> WorkspaceMembershipRepository:
    return WorkspaceMembershipRepository(db)


def get_workspace_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> WorkspaceRepository:
    return WorkspaceRepository(db)


def get_feature_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> FeatureRepository:
    return FeatureRepository(db)


def get_feedback_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> FeedbackRepository:
    return FeedbackRepository(db)


def get_feedback_batch_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> FeedbackBatchRepository:
    return FeedbackBatchRepository(db)


def get_prd_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> PRDRepository:
    return PRDRepository(db)


def get_roadmap_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> RoadmapRepository:
    return RoadmapRepository(db)


def get_release_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> ReleaseRepository:
    return ReleaseRepository(db)


def get_analytics_rollup_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AnalyticsDailyRollupRepository:
    return AnalyticsDailyRollupRepository(db)


def get_analytics_event_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AnalyticsEventRepository:
    return AnalyticsEventRepository(db)


def get_analytics_batch_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AnalyticsBatchRepository:
    return AnalyticsBatchRepository(db)


def get_feature_group_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> FeatureGroupRepository:
    return FeatureGroupRepository(db)


def get_customer_persona_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> CustomerPersonaRepository:
    return CustomerPersonaRepository(db)


def get_competitor_intel_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> CompetitorIntelRepository:
    return CompetitorIntelRepository(db)


def get_product_experiment_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> ProductExperimentRepository:
    return ProductExperimentRepository(db)


def get_customer_journey_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> CustomerJourneyRepository:
    return CustomerJourneyRepository(db)


def get_prioritization_scenario_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> PrioritizationScenarioRepository:
    return PrioritizationScenarioRepository(db)


def get_copilot_conversation_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> CopilotConversationRepository:
    return CopilotConversationRepository(db)


def get_copilot_message_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> CopilotMessageRepository:
    return CopilotMessageRepository(db)


def get_audit_log_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> AuditLogRepository:
    return AuditLogRepository(db)


def get_saved_report_repository(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
) -> SavedReportRepository:
    return SavedReportRepository(db)


# -------------------------------------------------------------------------
# Authentication & User Context Dependencies
# -------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    token: Optional[Union[HTTPAuthorizationCredentials, str]] = Depends(http_bearer),
    user_repo: UserRepository = Depends(get_user_repository),
    session_repo: AuthSessionRepository = Depends(get_auth_session_repository),
) -> User:
    """
    Extracts Bearer access token, verifies cryptographic signature,
    checks active session in database, and retrieves the authenticated User.
    Raises HTTP 401 Unauthorized for missing, invalid, expired, or revoked tokens.
    """
    raw_token: Optional[str] = (
        token.credentials if isinstance(token, HTTPAuthorizationCredentials) else token
    )

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(raw_token)
    except ExpiredTokenException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Enforce token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    session_id = payload.get("session_id")
    if not user_id or not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify session is actively valid in MongoDB (not revoked, not expired)
    auth_session = await session_repo.find_by_id_active(session_id)
    if not auth_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve User
    user = await user_repo.find_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach context to request state for downstream handlers
    request.state.current_user = user
    request.state.session_id = session_id
    request.state.session_family = payload.get("session_family")

    return user


async def get_optional_current_user(
    request: Request,
    token: Optional[Union[HTTPAuthorizationCredentials, str]] = Depends(http_bearer),
) -> Optional[User]:
    """
    Extracts and verifies Bearer token if provided.
    Returns authenticated User if valid, None if no token was provided.
    Raises HTTP 401 Unauthorized if a malformed, expired, or revoked token was provided.
    Does not require database access if no token was supplied.
    """
    raw_token: Optional[str] = (
        token.credentials if isinstance(token, HTTPAuthorizationCredentials) else token
    )
    if not raw_token:
        return None

    db = await get_mongo_db(request)
    user_repo = UserRepository(db)
    session_repo = AuthSessionRepository(db)

    return await get_current_user(
        request=request,
        token=raw_token,
        user_repo=user_repo,
        session_repo=session_repo,
    )


# -------------------------------------------------------------------------
# AI LLM Service Dependency
# -------------------------------------------------------------------------

def get_ai_service():
    """Provides the active LLMService singleton for AI endpoint handlers."""
    from app.ai.llm_service import get_llm_service
    return get_llm_service()

