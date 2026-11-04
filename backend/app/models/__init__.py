"""
ProductMind AI — Central Model Registry & Exports
Exports all 22 domain models covering all 10 product modules.
"""

from app.models.base import BaseMongoModel
from app.models.auth import (
    User,
    Workspace,
    WorkspaceSettings,
    WorkspaceMembership,
    AuthSession,
)
from app.models.feedback import (
    FeedbackBatch,
    FeedbackItem,
    RowErrorSample,
)
from app.models.analytics import (
    AnalyticsBatch,
    AnalyticsEvent,
    AnalyticsDailyRollup,
    FeatureMetric,
    FunnelStepMetric,
)
from app.models.intelligence import (
    FeatureGroup,
    SentimentDistribution,
    CustomerPersona,
    CompetitorIntel,
)
from app.models.planning import (
    Feature,
    FeatureComment,
    PRD,
    PRDSections,
    RoadmapItem,
    Release,
    ReleaseChecklistItem,
    ProductExperiment,
    CustomerJourney,
    Touchpoint,
    PrioritizationScenario,
    AdjustedFeature,
)
from app.models.copilot import (
    CopilotConversation,
    CopilotMessage,
    CopilotEvidence,
    CopilotModelInfo,
)
from app.models.audit import AuditLog
from app.models.reporting import SavedReport

__all__ = [
    "BaseMongoModel",
    "User",
    "Workspace",
    "WorkspaceSettings",
    "WorkspaceMembership",
    "AuthSession",
    "FeedbackBatch",
    "FeedbackItem",
    "RowErrorSample",
    "AnalyticsBatch",
    "AnalyticsEvent",
    "AnalyticsDailyRollup",
    "FeatureMetric",
    "FunnelStepMetric",
    "FeatureGroup",
    "SentimentDistribution",
    "CustomerPersona",
    "CompetitorIntel",
    "Feature",
    "FeatureComment",
    "PRD",
    "PRDSections",
    "RoadmapItem",
    "Release",
    "ReleaseChecklistItem",
    "ProductExperiment",
    "CustomerJourney",
    "Touchpoint",
    "PrioritizationScenario",
    "AdjustedFeature",
    "CopilotConversation",
    "CopilotMessage",
    "CopilotEvidence",
    "CopilotModelInfo",
    "AuditLog",
    "SavedReport",
]

