"""
ProductMind AI — PRD Schemas (Pydantic DTOs)
"""

from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import PRDStatus


class PRDCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    feature_id: Optional[str] = Field(default=None, alias="featureId")
    version: str = "1.0.0"
    status: PRDStatus = PRDStatus.DRAFT
    author: Optional[str] = None
    sections: Optional[Dict[str, str]] = None


class PRDUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    status: Optional[PRDStatus] = None
    version: Optional[str] = None
    sections: Optional[Dict[str, str]] = None


class PRDResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    feature_id: Optional[str] = Field(default=None, alias="featureId")
    title: str
    version: str
    status: PRDStatus
    author: Optional[str] = None
    sections: Dict[str, str] = Field(default_factory=dict)
    ai_generated: bool = Field(alias="aiGenerated")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

