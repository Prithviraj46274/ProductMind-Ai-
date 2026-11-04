"""
ProductMind AI — Analytics Schemas (Pydantic DTOs)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class AnalyticsDailyRollupResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    date: str
    active_users: int = Field(alias="activeUsers")
    total_sessions: int = Field(alias="totalSessions")
    total_events: int = Field(alias="totalEvents")
    avg_session_duration: float = Field(alias="avgSessionDuration")
    top_feature: Optional[str] = Field(default=None, alias="topFeature")
    feature_metrics: List[Dict[str, Any]] = Field(default_factory=list, alias="featureMetrics")
    funnel_metrics: List[Dict[str, Any]] = Field(default_factory=list, alias="funnelMetrics")
    calculated_at: Optional[datetime] = Field(default=None, alias="calculatedAt")


class AnalyticsEventCreate(BaseModel):
    event_name: str = Field(..., alias="eventName")
    event_type: str = Field(default="view", alias="eventType")
    event_timestamp: datetime = Field(..., alias="eventTimestamp")
    date: str
    actor_id: Optional[str] = Field(default=None, alias="actorId")
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    feature_name: str = Field(..., alias="featureName")
    duration_seconds: Optional[float] = Field(default=None, alias="durationSeconds")
    custom_properties: Dict[str, Any] = Field(default_factory=dict, alias="customProperties")

