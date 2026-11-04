"""
ProductMind AI Schemas Registry
"""

from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse, WorkspaceSettingsDTO
from app.schemas.feedback import FeedbackItemCreate, FeedbackItemUpdate, FeedbackItemResponse
from app.schemas.feature import FeatureCreate, FeatureUpdate, FeatureResponse
from app.schemas.analytics import AnalyticsDailyRollupResponse, AnalyticsEventCreate
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
    "FeedbackItemCreate",
    "FeedbackItemUpdate",
    "FeedbackItemResponse",
    "FeatureCreate",
    "FeatureUpdate",
    "FeatureResponse",
    "AnalyticsDailyRollupResponse",
    "AnalyticsEventCreate",
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

