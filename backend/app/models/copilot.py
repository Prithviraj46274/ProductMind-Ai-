"""
ProductMind AI — Copilot Domain Models
Matches Mongoose schemas for CopilotConversation and CopilotMessage.
"""

from datetime import datetime
from typing import Optional, List, Literal
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
    input_tokens: Optional[int] = Field(default=None, alias="inputTokens")
    output_tokens: Optional[int] = Field(default=None, alias="outputTokens")


class CopilotConversation(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    user_id: PyObjectId = Field(..., alias="userId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    request_id: Optional[str] = Field(default=None, alias="requestId", max_length=120)
    title: str = Field(default="Strategy Session", max_length=150)
    is_archived: bool = Field(default=False, alias="isArchived")
    message_count: int = Field(default=0, alias="messageCount")
    last_message_at: Optional[datetime] = Field(default_factory=utc_now, alias="lastMessageAt")


class CopilotMessage(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    conversation_id: PyObjectId = Field(..., alias="conversationId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    request_id: Optional[str] = Field(default=None, alias="requestId", max_length=120)
    role: CopilotRole = Field(default=CopilotRole.USER)
    content: str = Field(default="", max_length=10000)
    status: Literal["completed", "failed", "pending"] = Field(default="completed")
    error_message: Optional[str] = Field(default=None, alias="errorMessage", max_length=500)
    evidence: List[CopilotEvidence] = Field(default_factory=list)
    model_info: CopilotModelInfo = Field(default_factory=CopilotModelInfo, alias="modelInfo")
