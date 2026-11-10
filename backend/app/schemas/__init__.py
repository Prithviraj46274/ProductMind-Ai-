"""
ProductMind AI Schemas Registry
"""

from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    TokenRefreshResponse,
    MessageResponse,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
    WorkspaceResponse,
    WorkspaceSettingsDTO,
    WorkspaceUpdate,
)
from app.schemas.feedback import FeedbackItemCreate, FeedbackItemUpdate, FeedbackItemResponse
from app.schemas.feature import FeatureCreate, FeatureUpdate, FeatureResponse
from app.schemas.analytics import (
    AnalyticsBatchIngestResponse,
    AnalyticsBatchRequest,
    AnalyticsBatchRetryRequest,
    AnalyticsBatchStatusResponse,
    AnalyticsDailyRollupResponse,
    AnalyticsEventCreate,
    AnalyticsEventResponse,
    AnalyticsFeaturesResponse,
    AnalyticsFunnelResponse,
    AnalyticsOverviewResponse,
    AnalyticsUsageTrendsResponse,
)
from app.schemas.prd import PRDCreate, PRDUpdate, PRDResponse
from app.schemas.roadmap import RoadmapItemCreate, RoadmapItemUpdate, RoadmapItemResponse
from app.schemas.copilot import (
    CopilotConversationCreate,
    CopilotConversationResponse,
    CopilotMessageCreate,
    CopilotMessageResponse,
)
from app.schemas.audit_log import AuditLogCreate, AuditLogResponse

__all__ = [
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceResponse",
    "WorkspaceSettingsDTO",
    "WorkspaceMemberAdd",
    "WorkspaceMemberRoleUpdate",
    "WorkspaceMemberResponse",
    "FeedbackItemCreate",
    "FeedbackItemUpdate",
    "FeedbackItemResponse",
    "FeatureCreate",
    "FeatureUpdate",
    "FeatureResponse",
    "AnalyticsDailyRollupResponse",
    "AnalyticsEventCreate",
    "AnalyticsEventResponse",
    "AnalyticsBatchRequest",
    "AnalyticsBatchRetryRequest",
    "AnalyticsBatchIngestResponse",
    "AnalyticsBatchStatusResponse",
    "AnalyticsOverviewResponse",
    "AnalyticsUsageTrendsResponse",
    "AnalyticsFeaturesResponse",
    "AnalyticsFunnelResponse",
    "PRDCreate",
    "PRDUpdate",
    "PRDResponse",
    "RoadmapItemCreate",
    "RoadmapItemUpdate",
    "RoadmapItemResponse",
    "CopilotConversationCreate",
    "CopilotConversationResponse",
    "CopilotMessageCreate",
    "CopilotMessageResponse",
    "AuditLogCreate",
    "AuditLogResponse",
]
