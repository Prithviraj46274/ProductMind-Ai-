"""
ProductMind AI Repositories Registry
"""

from app.repositories.base import (
    BaseRepository,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.repositories.user_repository import (
    UserRepository,
    WorkspaceMembershipRepository,
)
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.repositories.feedback_repository import (
    FeedbackRepository,
    FeedbackBatchRepository,
)
from app.repositories.feature_repository import FeatureRepository
from app.repositories.analytics_repository import (
    AnalyticsDailyRollupRepository,
    AnalyticsEventRepository,
    AnalyticsBatchRepository,
)
from app.repositories.prd_repository import PRDRepository
from app.repositories.roadmap_repository import RoadmapRepository
from app.repositories.release_repository import ReleaseRepository
from app.repositories.copilot_repository import (
    CopilotConversationRepository,
    CopilotMessageRepository,
)
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.intelligence_repository import (
    FeatureGroupRepository,
    CustomerPersonaRepository,
    CompetitorIntelRepository,
    ProductExperimentRepository,
    CustomerJourneyRepository,
    PrioritizationScenarioRepository,
)
from app.repositories.reporting_repository import SavedReportRepository

__all__ = [
    "BaseRepository",
    "DuplicateEntityError",
    "EntityNotFoundError",
    "UserRepository",
    "WorkspaceMembershipRepository",
    "AuthSessionRepository",
    "WorkspaceRepository",
    "FeedbackRepository",
    "FeedbackBatchRepository",
    "FeatureRepository",
    "AnalyticsDailyRollupRepository",
    "AnalyticsEventRepository",
    "AnalyticsBatchRepository",
    "PRDRepository",
    "RoadmapRepository",
    "ReleaseRepository",
    "CopilotConversationRepository",
    "CopilotMessageRepository",
    "AuditLogRepository",
    "FeatureGroupRepository",
    "CustomerPersonaRepository",
    "CompetitorIntelRepository",
    "ProductExperimentRepository",
    "CustomerJourneyRepository",
    "PrioritizationScenarioRepository",
    "SavedReportRepository",
]

