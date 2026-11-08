"""
ProductMind AI — Intelligence & Clustering Domain Models
Matches Mongoose schemas for FeatureGroup, CustomerPersona, and CompetitorIntel.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId
from app.core.enums import FeedbackCategory, FeatureGroupStatus


class SentimentDistribution(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    positive: int = Field(default=0, alias="Positive", ge=0)
    neutral: int = Field(default=0, alias="Neutral", ge=0)
    negative: int = Field(default=0, alias="Negative", ge=0)


class FeatureGroup(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    title: str = Field(..., max_length=200)
    category: FeedbackCategory = Field(default=FeedbackCategory.FEATURE_REQUESTS)
    primary_tag: str = Field(default="general", alias="primaryTag")
    description: str = Field(default="", max_length=2000)
    status: FeatureGroupStatus = Field(default=FeatureGroupStatus.SUGGESTED)
    sentiment_distribution: SentimentDistribution = Field(
        default_factory=SentimentDistribution, alias="sentimentDistribution"
    )
    pain_points: List[str] = Field(default_factory=list, alias="painPoints")
    feedback_count: int = Field(default=0, alias="feedbackCount", ge=0)
    # AI Feature Intelligence extensions (backward-compatible)
    feature_summary: Optional[str] = Field(default=None, alias="featureSummary")
    related_feedback_ids: List[PyObjectId] = Field(default_factory=list, alias="relatedFeedbackIds")
    common_themes: List[str] = Field(default_factory=list, alias="commonThemes")
    evidence: List[str] = Field(default_factory=list)
    suggested_capability: Optional[str] = Field(default=None, alias="suggestedCapability")
    grouping_confidence: Optional[float] = Field(default=None, alias="groupingConfidence")
    grouping_reason: Optional[str] = Field(default=None, alias="groupingReason")
    unique_customer_count: int = Field(default=0, alias="uniqueCustomerCount", ge=0)
    urgency_distribution: Dict[str, int] = Field(default_factory=dict, alias="urgencyDistribution")
    ai_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="aiMetadata")
    promoted_feature_id: Optional[PyObjectId] = Field(default=None, alias="promotedFeatureId")
    merged_into_group_id: Optional[PyObjectId] = Field(default=None, alias="mergedIntoGroupId")
    reviewed_by: Optional[PyObjectId] = Field(default=None, alias="reviewedBy")
    reviewed_at: Optional[datetime] = Field(default=None, alias="reviewedAt")


class CustomerPersona(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    name: str = Field(..., max_length=100)
    role: str = Field(..., max_length=120)
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    company_type: Optional[str] = Field(default=None, alias="companyType", max_length=120)
    avatar: Optional[str] = Field(default=None, max_length=10)
    description: str = Field(default="", max_length=2000)
    goals: List[str] = Field(default_factory=list)
    frustrations: List[str] = Field(default_factory=list)
    needs: List[str] = Field(default_factory=list)
    feature_preferences: List[str] = Field(default_factory=list, alias="featurePreferences")
    sentiment_summary: Optional[str] = Field(default=None, alias="sentimentSummary", max_length=100)
    related_feedback_count: int = Field(default=0, alias="relatedFeedbackCount", ge=0)
    is_favorite: bool = Field(default=False, alias="isFavorite")


class CompetitorIntel(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    name: str = Field(..., max_length=120)
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    product_description: str = Field(default="", alias="productDescription", max_length=2000)
    website: str = Field(default="", max_length=300)
    target_audience: Optional[str] = Field(default=None, alias="targetAudience", max_length=200)
    key_features: List[str] = Field(default_factory=list, alias="keyFeatures")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    differentiators: List[str] = Field(default_factory=list)
    research_notes: str = Field(default="", alias="researchNotes", max_length=3000)
    last_reviewed: Optional[datetime] = Field(default_factory=utc_now, alias="lastReviewed")
