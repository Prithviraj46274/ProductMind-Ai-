"""
ProductMind AI — Feedback Schemas (Pydantic DTOs)
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import AliasChoices, BaseModel, Field, ConfigDict, field_validator
from app.core.enums import (
    FeedbackSourceType,
    FeedbackCategory,
    FeedbackSentiment,
    FeedbackPriority,
    FeedbackProcessingStatus,
)


class FeedbackItemCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str = Field(..., min_length=3, max_length=300)
    description: str = Field(..., max_length=5000)
    source_type: FeedbackSourceType = Field(default=FeedbackSourceType.MANUAL, alias="sourceType")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl", max_length=500)
    external_id: Optional[str] = Field(default=None, alias="externalId", max_length=120)
    customer_name: Optional[str] = Field(default=None, alias="customerName", max_length=120)
    customer_email: Optional[str] = Field(default=None, alias="customerEmail", max_length=150)
    company_name: Optional[str] = Field(default=None, alias="companyName", max_length=150)
    category: Optional[FeedbackCategory] = None
    sentiment: Optional[FeedbackSentiment] = None
    source_priority: Optional[FeedbackPriority] = Field(default=None, alias="sourcePriority")
    tags: List[str] = Field(default_factory=list, max_length=50)
    feedback_date: Optional[datetime] = Field(default=None, alias="feedbackDate")
    promoted_feature_id: Optional[str] = Field(
        default=None,
        alias="promotedFeatureId",
        validation_alias=AliasChoices("promotedFeatureId", "linkedFeatureId"),
        max_length=24,
    )

    @field_validator(
        "title",
        "description",
        "source_url",
        "external_id",
        "customer_name",
        "customer_email",
        "company_name",
        "promoted_feature_id",
        mode="before",
    )
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("tags")
    @classmethod
    def strip_tags(cls, values: List[str]) -> List[str]:
        trimmed = [value.strip() for value in values]
        if any(len(value) > 100 for value in trimmed):
            raise ValueError("Tag entries may not exceed 100 characters")
        return trimmed


class FeedbackItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[FeedbackCategory] = None
    sentiment: Optional[FeedbackSentiment] = None
    source_priority: Optional[FeedbackPriority] = Field(default=None, alias="sourcePriority")
    ai_predicted_priority: Optional[FeedbackPriority] = Field(default=None, alias="aiPredictedPriority")
    tags: Optional[List[str]] = None
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")
    promoted_feature_id: Optional[str] = Field(default=None, alias="promotedFeatureId")
    processing_status: Optional[FeedbackProcessingStatus] = Field(default=None, alias="processingStatus")


class FeedbackItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    title: str
    description: str
    source_type: FeedbackSourceType = Field(alias="sourceType")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl")
    external_id: Optional[str] = Field(default=None, alias="externalId")
    customer_name: Optional[str] = Field(default=None, alias="customerName")
    customer_email: Optional[str] = Field(default=None, alias="customerEmail")
    company_name: Optional[str] = Field(default=None, alias="companyName")
    category: Optional[FeedbackCategory] = None
    sentiment: Optional[FeedbackSentiment] = None
    source_priority: Optional[FeedbackPriority] = Field(default=None, alias="sourcePriority")
    ai_predicted_priority: Optional[FeedbackPriority] = Field(default=None, alias="aiPredictedPriority")
    tags: List[str] = Field(default_factory=list)
    batch_id: Optional[str] = Field(default=None, alias="batchId")
    feedback_date: Optional[datetime] = Field(default=None, alias="feedbackDate")
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")
    promoted_feature_id: Optional[str] = Field(default=None, alias="promotedFeatureId")
    processing_status: FeedbackProcessingStatus = Field(alias="processingStatus")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")


class FeedbackListResponse(BaseModel):
    items: List[FeedbackItemResponse]
    total: int
    page: int
    limit: int
    pages: int


class FeedbackBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[Dict[str, Any]] = Field(..., min_length=1, max_length=500)


class FeedbackBatchRetryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(alias="rowNumber", ge=1)
    item: Dict[str, Any]


class FeedbackBatchRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[FeedbackBatchRetryItem] = Field(..., min_length=1, max_length=500)


class FeedbackRowError(BaseModel):
    field: str
    message: str


class FeedbackBatchRowResult(BaseModel):
    row_number: int = Field(alias="rowNumber")
    status: Literal["accepted", "duplicate", "rejected"]
    feedback_id: Optional[str] = Field(default=None, alias="feedbackId")
    errors: List[FeedbackRowError] = Field(default_factory=list)


class FeedbackBatchIngestResponse(BaseModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    status: str
    total_rows: int = Field(alias="totalRows")
    accepted_rows: int = Field(alias="acceptedRows")
    rejected_rows: int = Field(alias="rejectedRows")
    duplicate_rows: int = Field(alias="duplicateRows")
    results: List[FeedbackBatchRowResult]


class FeedbackBatchStatusResponse(BaseModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    status: str
    total_rows: int = Field(alias="totalRows")
    accepted_rows: int = Field(alias="acceptedRows")
    rejected_rows: int = Field(alias="rejectedRows")
    duplicate_rows: int = Field(alias="duplicateRows")
    error_summary: List[Dict[str, Any]] = Field(alias="errorSummary")
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")
