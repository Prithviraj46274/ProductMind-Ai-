"""
ProductMind AI — Product Analytics Domain Models
Matches Mongoose schemas for AnalyticsBatch, AnalyticsEvent, and AnalyticsDailyRollup.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId


class AnalyticsBatch(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    uploaded_by: PyObjectId = Field(..., alias="uploadedBy")
    file_name: str = Field(..., alias="fileName", max_length=255)
    file_size: int = Field(default=0, alias="fileSize", ge=0)
    file_hash: Optional[str] = Field(default=None, alias="fileHash")
    source_type: str = Field(default="csv", alias="sourceType")
    status: str = Field(default="pending")
    total_rows: int = Field(default=0, alias="totalRows", ge=0)
    accepted_rows: int = Field(default=0, alias="acceptedRows", ge=0)
    rejected_rows: int = Field(default=0, alias="rejectedRows", ge=0)
    detected_columns: List[str] = Field(default_factory=list, alias="detectedColumns")
    mapped_columns: Dict[str, str] = Field(default_factory=dict, alias="mappedColumns")
    error_summary: List[Dict[str, Any]] = Field(default_factory=list, alias="errorSummary")
    started_at: Optional[datetime] = Field(default_factory=utc_now, alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")


class AnalyticsEvent(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    batch_id: Optional[PyObjectId] = Field(default=None, alias="batchId")
    event_id: Optional[str] = Field(default=None, alias="eventId", max_length=120)
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    event_name: str = Field(..., alias="eventName", max_length=100)
    event_type: str = Field(default="view", alias="eventType", max_length=50)
    event_timestamp: datetime = Field(..., alias="eventTimestamp")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    actor_id: Optional[str] = Field(default=None, alias="actorId", max_length=100)
    session_id: Optional[str] = Field(default=None, alias="sessionId", max_length=120)
    feature_name: str = Field(..., alias="featureName", max_length=120)
    duration_seconds: Optional[float] = Field(default=None, alias="durationSeconds", ge=0.0)
    custom_properties: Dict[str, Any] = Field(default_factory=dict, alias="customProperties")


class FeatureMetric(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    name: str
    event_count: int = Field(default=0, alias="eventCount", ge=0)
    unique_users: int = Field(default=0, alias="uniqueUsers", ge=0)
    adoption_percent: float = Field(default=0.0, alias="adoptionPercent", ge=0.0, le=100.0)
    avg_duration_sec: float = Field(default=0.0, alias="avgDurationSec", ge=0.0)
    completion_rate: float = Field(default=0.0, alias="completionRate", ge=0.0, le=100.0)


class FunnelStepMetric(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    step: str
    users: int = Field(default=0, ge=0)
    conversion_rate: float = Field(default=0.0, alias="conversionRate", ge=0.0, le=100.0)
    drop_off_rate: float = Field(default=0.0, alias="dropOffRate", ge=0.0, le=100.0)


class AnalyticsDailyRollup(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    active_users: int = Field(default=0, alias="activeUsers", ge=0)
    total_sessions: int = Field(default=0, alias="totalSessions", ge=0)
    total_events: int = Field(default=0, alias="totalEvents", ge=0)
    avg_session_duration: float = Field(default=0.0, alias="avgSessionDuration", ge=0.0)
    top_feature: Optional[str] = Field(default=None, alias="topFeature")
    feature_metrics: List[FeatureMetric] = Field(default_factory=list, alias="featureMetrics")
    funnel_metrics: List[FunnelStepMetric] = Field(default_factory=list, alias="funnelMetrics")
    calculated_at: Optional[datetime] = Field(default_factory=utc_now, alias="calculatedAt")
