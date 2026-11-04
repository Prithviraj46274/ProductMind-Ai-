"""
ProductMind AI — Central Domain Enums & Constants
Matches all schemas and business logic defined in server/src/constants/enums.js.
"""

from enum import Enum
from typing import Dict, Any


class UserRole(str, Enum):
    LEAD_PRODUCT_ARCHITECT = "Lead Product Architect"
    VP_PRODUCT = "VP of Product & Strategy"
    HEAD_PRODUCT_OPS = "Head of Product Operations"
    PRODUCT_MANAGER = "Product Manager"
    ENGINEERING_LEAD = "Staff Software Architect"
    VIEWER = "Viewer"
    ADMIN = "Workspace Admin"


class PlatformRole(str, Enum):
    USER = "user"
    PLATFORM_ADMIN = "platform_admin"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    INVITED = "invited"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class WorkspacePlan(str, Enum):
    STARTER = "Starter Tier"
    PRO = "Pro Tier"
    ENTERPRISE = "Enterprise Tier"


class FeedbackSourceType(str, Enum):
    MANUAL = "manual"
    CSV = "csv"
    JSON = "json"
    SUPPORT_TICKET = "support_ticket"
    GITHUB = "github"
    JIRA = "jira"
    SLACK = "slack"


class FeedbackSentiment(str, Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"


class FeedbackPriority(str, Enum):
    URGENT = "Urgent"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class FeedbackCategory(str, Enum):
    PERFORMANCE = "Performance"
    INTEGRATIONS = "Integrations"
    USABILITY = "Usability"
    RELIABILITY = "Reliability"
    PRICING = "Pricing"
    SATISFACTION = "Satisfaction"
    FEATURE_REQUESTS = "Feature Requests"
    GENERAL = "General"


class FeedbackProcessingStatus(str, Enum):
    RAW = "raw"
    PROCESSED = "processed"
    CLASSIFIED = "classified"
    AGGREGATED = "aggregated"
    ARCHIVED = "archived"


class FeatureGroupStatus(str, Enum):
    SUGGESTED = "suggested"
    APPROVED = "approved"
    MERGED = "merged"
    REJECTED = "rejected"


class FeatureStatus(str, Enum):
    BACKLOG = "Backlog"
    EVALUATING = "Evaluating"
    IN_PLANNING = "In Planning"
    IN_DEVELOPMENT = "In Development"
    READY_FOR_RELEASE = "Ready for Release"
    LAUNCHED = "Launched"


class PriorityTier(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class PRDStatus(str, Enum):
    DRAFT = "Draft"
    IN_REVIEW = "In Review"
    APPROVED = "Approved"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"


class RoadmapStatus(str, Enum):
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    IN_REVIEW = "In Review"
    SHIPPED = "Shipped"


class ReleaseStatus(str, Enum):
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    READY = "Ready"
    SHIPPED = "Shipped"
    BLOCKED = "Blocked"


class ExperimentStatus(str, Enum):
    DRAFT = "Draft"
    RUNNING = "Running"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class ExperimentConclusion(str, Enum):
    ROLL_OUT = "Roll Out"
    CONTINUE = "Continue"
    ITERATE = "Iterate"
    ABANDON = "Abandon"


class CopilotRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    MERGED = "merged"
    APPROVED = "approved"
    RESTORED = "restored"


class AuditEntityType(str, Enum):
    FEEDBACK = "feedback"
    FEATURE = "feature"
    FEATURE_GROUP = "feature_group"
    PRD = "prd"
    ROADMAP = "roadmap"
    RELEASE = "release"
    EXPERIMENT = "experiment"
    PERSONA = "persona"
    WORKSPACE = "workspace"
    ANALYTICS = "analytics"


class SavedReportType(str, Enum):
    EXECUTIVE_KPI = "executive_kpi"
    SENTIMENT_DISTRIBUTION = "sentiment_distribution"
    FEATURE_PRIORITIZATION = "feature_prioritization"
    ANALYTICS_FUNNEL = "analytics_funnel"
    CUSTOM_DASHBOARD = "custom_dashboard"


# -------------------------------------------------------------------------
# Exact 4-factor Prioritization Scoring Formula
# Formula: (0.35 * Impact) + (0.30 * Urgency) + (0.20 * Demand) + (0.15 * BusinessValue)
# -------------------------------------------------------------------------
FACTOR_WEIGHTS: Dict[str, float] = {
    "customerImpact": 0.35,
    "urgency": 0.30,
    "demand": 0.20,
    "businessValue": 0.15,
}


def calculate_priority_score(
    customer_impact: float = 5.0,
    urgency: float = 5.0,
    demand: float = 5.0,
    business_value: float = 5.0,
) -> float:
    """Calculates weighted 4-factor priority score rounded to 2 decimal places."""
    score = (
        (FACTOR_WEIGHTS["customerImpact"] * customer_impact)
        + (FACTOR_WEIGHTS["urgency"] * urgency)
        + (FACTOR_WEIGHTS["demand"] * demand)
        + (FACTOR_WEIGHTS["businessValue"] * business_value)
    )
    return round(score, 2)


def get_priority_tier(score: float) -> PriorityTier:
    """Maps score to priority tier matching frontend and database boundaries."""
    if score >= 8.5:
        return PriorityTier.CRITICAL
    if score >= 7.0:
        return PriorityTier.HIGH
    if score >= 5.0:
        return PriorityTier.MEDIUM
    return PriorityTier.LOW
