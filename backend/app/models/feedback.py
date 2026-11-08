"""
ProductMind AI — Feedback Domain Models
Matches Mongoose schemas for FeedbackBatch and FeedbackItem.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId
from app.core.enums import (
    FeedbackSourceType,
    FeedbackCategory,
    FeedbackSentiment,
    FeedbackPriority,
    FeedbackProcessingStatus,
)


class RowErrorSample(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    row_number: int = Field(..., alias="rowNumber")
    field: str = Field(default="general")
    message: str = Field(..., max_length=200)


class FeedbackBatch(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    uploaded_by: PyObjectId = Field(..., alias="uploadedBy")
    source_type: FeedbackSourceType = Field(default=FeedbackSourceType.CSV, alias="sourceType")
    file_name: str = Field(default="import.csv", alias="fileName", max_length=255)
    file_hash: Optional[str] = Field(default=None, alias="fileHash")
    status: str = Field(default="pending")
    field_mappings: Dict[str, str] = Field(default_factory=dict, alias="fieldMappings")
    total_rows: int = Field(default=0, alias="totalRows", ge=0)
    accepted_rows: int = Field(default=0, alias="acceptedRows", ge=0)
    rejected_rows: int = Field(default=0, alias="rejectedRows", ge=0)
    duplicate_rows: int = Field(default=0, alias="duplicateRows", ge=0)
    error_summary: List[RowErrorSample] = Field(default_factory=list, alias="errorSummary")
    started_at: Optional[datetime] = Field(default_factory=utc_now, alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")


class FeedbackItem(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    batch_id: Optional[PyObjectId] = Field(default=None, alias="batchId")
    external_id: Optional[str] = Field(default=None, alias="externalId", max_length=120)
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    source_type: FeedbackSourceType = Field(default=FeedbackSourceType.MANUAL, alias="sourceType")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl", max_length=500)
    title: str = Field(..., min_length=3, max_length=300)
    description: str = Field(..., max_length=5000)
    customer_name: Optional[str] = Field(default=None, alias="customerName", max_length=120)
    customer_email: Optional[str] = Field(default=None, alias="customerEmail", max_length=150)
    company_name: Optional[str] = Field(default=None, alias="companyName", max_length=150)
    category: Optional[FeedbackCategory] = Field(default=None)
    sentiment: Optional[FeedbackSentiment] = Field(default=None)
    source_priority: Optional[FeedbackPriority] = Field(default=None, alias="sourcePriority")
    ai_predicted_priority: Optional[FeedbackPriority] = Field(default=None, alias="aiPredictedPriority")
    source_tags: List[str] = Field(default_factory=list, alias="sourceTags")
    ai_themes: List[str] = Field(default_factory=list, alias="aiThemes")
    tags: List[str] = Field(default_factory=list)
    feedback_date: Optional[datetime] = Field(default_factory=utc_now, alias="feedbackDate")
    feature_group_id: Optional[PyObjectId] = Field(default=None, alias="featureGroupId")
    promoted_feature_id: Optional[PyObjectId] = Field(default=None, alias="promotedFeatureId")
    classification_confidence: Optional[float] = Field(default=None, alias="classificationConfidence", ge=0.0, le=1.0)
    processing_status: FeedbackProcessingStatus = Field(default=FeedbackProcessingStatus.RAW, alias="processingStatus")
    embedding: Optional[List[float]] = Field(default=None)
    ai_analysis: Optional[Dict[str, Any]] = Field(default=None, alias="aiAnalysis")
    analyzed_at: Optional[datetime] = Field(default=None, alias="analyzedAt")
