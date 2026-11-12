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
    message_count: int = Field(default=0, alias="messageCount")
    last_message_at: Optional[datetime] = Field(default=None, alias="lastMessageAt")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")


class CopilotMessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    conversation_id: str = Field(alias="conversationId")
    role: CopilotRole
    content: str
    status: str = "completed"
    request_id: Optional[str] = Field(default=None, alias="requestId")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    model_info: Dict[str, Any] = Field(default_factory=dict, alias="modelInfo")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")


class CopilotTurnResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    conversation: CopilotConversationResponse
    user_message: CopilotMessageResponse = Field(alias="userMessage")
    assistant_message: CopilotMessageResponse = Field(alias="assistantMessage")
    retried: bool = False


class CopilotChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    workspace_id: str = Field(..., alias="workspaceId", min_length=1)
    conversation_id: Optional[str] = Field(default=None, alias="conversationId")
    message: str = Field(..., min_length=1, max_length=2000)
    request_id: Optional[str] = Field(default=None, alias="requestId", max_length=120)


class CopilotConversationCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    workspace_id: str = Field(..., alias="workspaceId", min_length=1)
    title: Optional[str] = Field(default="Strategy Session", max_length=150)
    request_id: Optional[str] = Field(default=None, alias="requestId", max_length=120)


class CopilotConversationRenameRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    workspace_id: str = Field(..., alias="workspaceId", min_length=1)
    title: str = Field(..., min_length=1, max_length=150)


class CopilotConversationListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    conversations: List[CopilotConversationResponse]
    total: int
    skip: int
    limit: int


class CopilotConversationDetailResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    conversation: CopilotConversationResponse
    messages: List[CopilotMessageResponse]
    total: int
    skip: int
    limit: int


class CopilotArchiveResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    success: bool = True
    conversation_id: str = Field(alias="conversationId")
    is_archived: bool = Field(default=True, alias="isArchived")

