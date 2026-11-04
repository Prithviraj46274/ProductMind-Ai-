"""
ProductMind AI — Roadmap Schemas (Pydantic DTOs)
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import RoadmapStatus, FeedbackPriority


class RoadmapItemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    feature_id: Optional[str] = Field(default=None, alias="featureId")
    release_id: Optional[str] = Field(default=None, alias="releaseId")
    status: RoadmapStatus = RoadmapStatus.PLANNED
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    owner: Optional[str] = None
    start_date: str = Field(..., alias="startDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    target_date: str = Field(..., alias="targetDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    milestone: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    notes: str = ""


class RoadmapItemUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = None
    status: Optional[RoadmapStatus] = None
    priority: Optional[FeedbackPriority] = None
    owner: Optional[str] = None
    start_date: Optional[str] = Field(default=None, alias="startDate")
    target_date: Optional[str] = Field(default=None, alias="targetDate")
    milestone: Optional[str] = None
    progress: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    notes: Optional[str] = None


class RoadmapItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    feature_id: Optional[str] = Field(default=None, alias="featureId")
    release_id: Optional[str] = Field(default=None, alias="releaseId")
    title: str
    description: str
    status: RoadmapStatus
    priority: FeedbackPriority
    owner: Optional[str] = None
    start_date: str = Field(alias="startDate")
    target_date: str = Field(alias="targetDate")
    milestone: Optional[str] = None
    progress: float
    notes: str
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

