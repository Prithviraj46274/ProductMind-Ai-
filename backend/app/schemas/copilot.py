"""
ProductMind AI — Copilot Schemas (Pydantic DTOs)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.core.enums import CopilotRole


class CopilotMessageCreate(BaseModel):
    role: CopilotRole = CopilotRole.USER
    content: str = Field(..., max_length=10000)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


class CopilotConversationCreate(BaseModel):
    title: str = Field(default="Strategy Session", max_length=150)


class CopilotConversationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    workspace_id: str = Field(alias="workspaceId")
    user_id: str = Field(alias="userId")
    title: str
    is_archived: bool = Field(alias="isArchived")
    last_message_at: Optional[datetime] = Field(default=None, alias="lastMessageAt")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")


class CopilotMessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    conversation_id: str = Field(alias="conversationId")
    role: CopilotRole
    content: str
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    model_info: Dict[str, Any] = Field(default_factory=dict, alias="modelInfo")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

