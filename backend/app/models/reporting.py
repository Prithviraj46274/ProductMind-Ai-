"""
ProductMind AI — Saved Report Domain Model
Matches Mongoose schema for SavedReport.
"""

from typing import Optional, List, Dict, Any
from pydantic import Field
from bson import ObjectId

from app.models.base import BaseMongoModel
from app.database.objectid import PyObjectId
from app.core.enums import SavedReportType


class SavedReport(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    created_by: PyObjectId = Field(..., alias="createdBy")
    title: str = Field(..., max_length=150)
    report_type: SavedReportType = Field(default=SavedReportType.EXECUTIVE_KPI, alias="reportType")
    filters: Dict[str, Any] = Field(default_factory=lambda: {"timeRange": "30d"})
    layout_config: List[str] = Field(
        default_factory=lambda: ["kpis", "trends", "sentiment", "priorities"],
        alias="layoutConfig",
    )
    is_favorite: bool = Field(default=False, alias="isFavorite")

