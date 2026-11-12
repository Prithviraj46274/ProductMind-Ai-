"""
ProductMind AI — Analytics Schemas (Pydantic DTOs)
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)


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
    ingested_metrics: Optional[Dict[str, Any]] = Field(default=None, alias="ingestedMetrics")
    calculated_at: Optional[datetime] = Field(default=None, alias="calculatedAt")


class AnalyticsEventCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    event_id: str = Field(alias="eventId", min_length=1, max_length=120)
    event_name: str = Field(alias="eventName", min_length=1, max_length=100)
    event_type: str = Field(alias="eventType", min_length=1, max_length=50)
    event_timestamp: datetime = Field(alias="eventTimestamp")
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    feature_id: Optional[str] = Field(default=None, alias="featureId", max_length=24)
    feature_name: Optional[str] = Field(default=None, alias="featureName", max_length=120)
    actor_id: Optional[str] = Field(default=None, alias="actorId", max_length=100)
    session_id: Optional[str] = Field(default=None, alias="sessionId", max_length=120)
    duration_seconds: Optional[float] = Field(
        default=None,
        alias="durationSeconds",
        ge=0.0,
        allow_inf_nan=False,
    )
    custom_properties: Dict[str, Any] = Field(default_factory=dict, alias="customProperties")

    @field_validator(
        "event_id",
        "event_name",
        "event_type",
        "feature_id",
        "feature_name",
        "actor_id",
        "session_id",
        mode="before",
    )
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None

    @field_validator("event_timestamp", mode="before")
    @classmethod
    def require_rfc3339_timestamp(cls, value: Any) -> Any:
        if isinstance(value, str) and not _RFC3339_PATTERN.fullmatch(value):
            raise ValueError("eventTimestamp must be an RFC3339 timestamp with a timezone")
        if isinstance(value, str):
            value = value[:10] + "T" + value[11:]
            if value.endswith("z"):
                value = value[:-1] + "Z"
        return value

    @field_validator("event_timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("eventTimestamp must include a timezone")
        return value

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            date.fromisoformat(value)
        return value

    @field_validator("custom_properties")
    @classmethod
    def disallow_unapproved_custom_properties(
        cls,
        value: Dict[str, Any],
    ) -> Dict[str, Any]:
        if value:
            raise ValueError("customProperties must be empty until properties are approved")
        return value


class AnalyticsBatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: List[Any] = Field(..., min_length=1, max_length=500)
    file_name: Optional[str] = Field(default=None, alias="fileName", max_length=255)
    source_type: Optional[Literal["csv", "json"]] = Field(default=None, alias="sourceType")
    detected_columns: List[str] = Field(default_factory=list, alias="detectedColumns", max_length=100)
    mapped_columns: Dict[str, str] = Field(default_factory=dict, alias="mappedColumns")


class AnalyticsBatchRetryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    row_number: int = Field(alias="rowNumber", ge=1)
    item: Any


class AnalyticsBatchRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[AnalyticsBatchRetryItem] = Field(..., min_length=1, max_length=500)

    @field_validator("items")
    @classmethod
    def require_unique_row_numbers(
        cls,
        values: List[AnalyticsBatchRetryItem],
    ) -> List[AnalyticsBatchRetryItem]:
        row_numbers = [item.row_number for item in values]
        if len(row_numbers) != len(set(row_numbers)):
            raise ValueError("rowNumber values must be unique")
        return values


class AnalyticsBatchRowResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    row_number: int = Field(alias="rowNumber")
    status: Literal["accepted", "duplicate", "rejected"]
    event_id: Optional[str] = Field(default=None, alias="eventId")
    errors: List[Dict[str, str]] = Field(default_factory=list)


class AnalyticsBatchIngestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    workspace_id: str = Field(alias="workspaceId")
    status: str
    total_rows: int = Field(alias="totalRows")
    accepted_rows: int = Field(alias="acceptedRows")
    rejected_rows: int = Field(alias="rejectedRows")
    duplicate_rows: int = Field(alias="duplicateRows")
    results: List[AnalyticsBatchRowResult]


class AnalyticsBatchStatusResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    workspace_id: str = Field(alias="workspaceId")
    file_name: Optional[str] = Field(default=None, alias="fileName")
    source_type: Optional[str] = Field(default=None, alias="sourceType")
    status: str
    total_rows: int = Field(alias="totalRows")
    accepted_rows: int = Field(alias="acceptedRows")
    rejected_rows: int = Field(alias="rejectedRows")
    duplicate_rows: int = Field(alias="duplicateRows")
    error_summary: List[Dict[str, Any]] = Field(alias="errorSummary")
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")


class AnalyticsEventResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    workspace_id: str = Field(alias="workspaceId")
    batch_id: Optional[str] = Field(default=None, alias="batchId")
    event_id: str = Field(alias="eventId")
    event_name: str = Field(alias="eventName")
    event_type: str = Field(alias="eventType")
    event_timestamp: datetime = Field(alias="eventTimestamp")
    date: str
    feature_id: Optional[str] = Field(default=None, alias="featureId")
    feature_name: Optional[str] = Field(default=None, alias="featureName")
    actor_id: Optional[str] = Field(default=None, alias="actorId")
    session_id: Optional[str] = Field(default=None, alias="sessionId")
    duration_seconds: Optional[float] = Field(default=None, alias="durationSeconds")


class AnalyticsDateRange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    capped: bool = False


class AnalyticsCoverage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    state: Literal["no_data", "partial", "observed"]
    total_events: int = Field(alias="totalEvents", ge=0)
    events_with_actor_id: int = Field(alias="eventsWithActorId", ge=0)
    events_with_session_id: int = Field(alias="eventsWithSessionId", ge=0)
    raw_events_available: Optional[int] = Field(
        default=None,
        alias="rawEventsAvailable",
        ge=0,
    )


class AnalyticsOverviewData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    total_events: int = Field(alias="totalEvents", ge=0)
    active_users: Optional[int] = Field(default=None, alias="activeUsers", ge=0)
    sessions: Optional[int] = Field(default=None, ge=0)
    accounts: Optional[int] = None
    avg_event_duration_seconds: Optional[float] = Field(
        default=None,
        alias="avgEventDurationSeconds",
        ge=0.0,
    )
    avg_session_duration_seconds: Optional[float] = Field(
        default=None,
        alias="avgSessionDurationSeconds",
        ge=0.0,
    )
    coverage: AnalyticsCoverage
    observed_days: int = Field(alias="observedDays", ge=0)
    last_event_at: Optional[datetime] = Field(default=None, alias="lastEventAt")
    calculated_at: datetime = Field(alias="calculatedAt")
    date_range: AnalyticsDateRange = Field(alias="dateRange")


class AnalyticsOverviewResponse(BaseModel):
    data: AnalyticsOverviewData


class AnalyticsUsageTrendPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    events: int = Field(ge=0)
    active_users: Optional[int] = Field(default=None, alias="activeUsers", ge=0)
    sessions: Optional[int] = Field(default=None, ge=0)
    avg_event_duration_seconds: Optional[float] = Field(
        default=None,
        alias="avgEventDurationSeconds",
        ge=0.0,
    )
    coverage: AnalyticsCoverage
    last_event_at: Optional[datetime] = Field(default=None, alias="lastEventAt")


class AnalyticsUsageTrendsData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: List[AnalyticsUsageTrendPoint]
    coverage: AnalyticsCoverage
    observed_days: int = Field(alias="observedDays", ge=0)
    last_event_at: Optional[datetime] = Field(default=None, alias="lastEventAt")
    calculated_at: datetime = Field(alias="calculatedAt")
    date_range: AnalyticsDateRange = Field(alias="dateRange")


class AnalyticsUsageTrendsResponse(BaseModel):
    data: AnalyticsUsageTrendsData


class AnalyticsFeatureMetricResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    event_count: int = Field(alias="eventCount", ge=0)
    events_with_actor_id: int = Field(default=0, alias="eventsWithActorId", ge=0)
    unique_users: Optional[int] = Field(default=None, alias="uniqueUsers", ge=0)
    adoption_percent: Optional[float] = Field(
        default=None,
        alias="adoptionPercent",
        ge=0.0,
        le=100.0,
    )
    avg_event_duration_seconds: Optional[float] = Field(
        default=None,
        alias="avgEventDurationSeconds",
        ge=0.0,
    )
    duration_sample_count: int = Field(default=0, alias="durationSampleCount", ge=0)
    previous_event_count: Optional[int] = Field(default=None, alias="previousEventCount", ge=0)
    trend_delta_percent: Optional[float] = Field(default=None, alias="trendDeltaPercent")


class AnalyticsFeaturesData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: List[AnalyticsFeatureMetricResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    coverage: AnalyticsCoverage
    observed_days: int = Field(alias="observedDays", ge=0)
    last_event_at: Optional[datetime] = Field(default=None, alias="lastEventAt")
    calculated_at: datetime = Field(alias="calculatedAt")
    date_range: AnalyticsDateRange = Field(alias="dateRange")


class AnalyticsFeaturesResponse(BaseModel):
    data: AnalyticsFeaturesData


class AnalyticsFunnelStepResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    step: str
    order: int = Field(ge=1)
    users: int = Field(ge=0)
    conversion_rate: float = Field(alias="conversionRate", ge=0.0, le=100.0)
    step_conversion_rate: float = Field(alias="stepConversionRate", ge=0.0, le=100.0)
    drop_off_count: int = Field(alias="dropOffCount", ge=0)
    drop_off_rate: float = Field(alias="dropOffRate", ge=0.0, le=100.0)


class AnalyticsFunnelData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool = False
    reason: Optional[str] = None
    steps: List[AnalyticsFunnelStepResponse] = Field(default_factory=list)
    available_events: List[str] = Field(default_factory=list, alias="availableEvents")
    coverage: AnalyticsCoverage
    observed_days: int = Field(alias="observedDays", ge=0)
    last_event_at: Optional[datetime] = Field(default=None, alias="lastEventAt")
    calculated_at: datetime = Field(alias="calculatedAt")
    date_range: AnalyticsDateRange = Field(alias="dateRange")


class AnalyticsFunnelResponse(BaseModel):
    data: AnalyticsFunnelData
