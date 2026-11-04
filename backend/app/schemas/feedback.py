"""
ProductMind AI — Feedback Schemas (Pydantic DTOs)
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import (
    FeedbackSourceType,
    FeedbackCategory,
    FeedbackSentiment,
    FeedbackPriority,
    FeedbackProcessingStatus,
)


class FeedbackItemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    description: str = Field(..., max_length=5000)
    source_type: FeedbackSourceType = Field(default=FeedbackSourceType.MANUAL, alias="sourceType")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl")
    external_id: Optional[str] = Field(default=None, alias="externalId")
    customer_name: Optional[str] = Field(default=None, alias="customerName")
    customer_email: Optional[str] = Field(default=None, alias="customerEmail")
    company_name: Optional[str] = Field(default=None, alias="companyName")
    category: Optional[FeedbackCategory] = None
    sentiment: Optional[FeedbackSentiment] = None
    source_priority: Optional[FeedbackPriority] = Field(default=None, alias="sourcePriority")
    tags: List[str] = Field(default_factory=list)
    feedback_date: Optional[datetime] = Field(default=None, alias="feedbackDate")


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
    category: Optional[FeedbackCategory] = None
    sentiment: Optional[FeedbackSentiment] = None
    source_priority: Optional[FeedbackPriority] = Field(default=None, alias="sourcePriority")
    ai_predicted_priority: Optional[FeedbackPriority] = Field(default=None, alias="aiPredictedPriority")
    tags: List[str] = Field(default_factory=list)
    feedback_date: Optional[datetime] = Field(default=None, alias="feedbackDate")
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")
    promoted_feature_id: Optional[str] = Field(default=None, alias="promotedFeatureId")
    processing_status: FeedbackProcessingStatus = Field(alias="processingStatus")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

