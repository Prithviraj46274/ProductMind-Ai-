"""
ProductMind AI — Feature Schemas (Pydantic DTOs)
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import FeatureStatus, PriorityTier


class FeatureCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., max_length=5000)
    customer_impact: float = Field(default=5.0, alias="customerImpact", ge=1.0, le=10.0)
    urgency: float = Field(default=5.0, ge=1.0, le=10.0)
    demand: float = Field(default=5.0, ge=1.0, le=10.0)
    business_value: float = Field(default=5.0, alias="businessValue", ge=1.0, le=10.0)
    status: FeatureStatus = FeatureStatus.IN_PLANNING
    owner: Optional[str] = None
    target_release: Optional[str] = Field(default=None, alias="targetRelease")
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")


class FeatureUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    customer_impact: Optional[float] = Field(default=None, alias="customerImpact", ge=1.0, le=10.0)
    urgency: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    demand: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    business_value: Optional[float] = Field(default=None, alias="businessValue", ge=1.0, le=10.0)
    status: Optional[FeatureStatus] = None
    owner: Optional[str] = None
    target_release: Optional[str] = Field(default=None, alias="targetRelease")
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")


class FeatureResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    name: str
    description: str
    customer_impact: float = Field(alias="customerImpact")
    urgency: float
    demand: float
    business_value: float = Field(alias="businessValue")
    score: float
    priority_tier: PriorityTier = Field(alias="priorityTier")
    status: FeatureStatus
    owner: Optional[str] = None
    target_release: Optional[str] = Field(default=None, alias="targetRelease")
    feature_group_id: Optional[str] = Field(default=None, alias="featureGroupId")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

