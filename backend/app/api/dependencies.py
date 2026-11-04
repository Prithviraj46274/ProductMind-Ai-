"""
ProductMind AI — FastAPI Dependency Injection Layer
Provides reusable, non-duplicating dependencies for MongoDB clients, databases,
collection registries, and domain repositories.
"""

from typing import Type
from fastapi import Request, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.database.collections import Collections
from app.database.connection import MongoDBManager
from app.repositories import (
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
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
