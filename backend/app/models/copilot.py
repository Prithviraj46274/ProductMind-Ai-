"""
ProductMind AI — Copilot Domain Models
Matches Mongoose schemas for CopilotConversation and CopilotMessage.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId
from app.core.enums import CopilotRole


class CopilotEvidence(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    type: str
    label: str
    path: str
    count: int = 0
    entity_id: Optional[str] = Field(default=None, alias="entityId")


class CopilotModelInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    provider: str = "deterministic-nlp"
    model_name: str = Field(default="productmind-core-v1", alias="modelName")
    tokens_used: int = Field(default=0, alias="tokensUsed")


class CopilotConversation(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    user_id: PyObjectId = Field(..., alias="userId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    title: str = Field(default="Strategy Session", max_length=150)
    is_archived: bool = Field(default=False, alias="isArchived")
    last_message_at: Optional[datetime] = Field(default_factory=utc_now, alias="lastMessageAt")


class CopilotMessage(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    conversation_id: PyObjectId = Field(..., alias="conversationId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    role: CopilotRole = Field(default=CopilotRole.USER)
    content: str = Field(..., max_length=10000)
    evidence: List[CopilotEvidence] = Field(default_factory=list)
    model_info: CopilotModelInfo = Field(default_factory=CopilotModelInfo, alias="modelInfo")
