"""
ProductMind AI — Phase 4.5: Conversational Copilot REST API Router
Thin, workspace-authorized FastAPI layer delegating to CopilotConversationService.
"""

import logging
from typing import TYPE_CHECKING
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.exceptions import (
    AIAuthenticationException,
    AIConfigurationException,
    AIProviderException,
    AIRateLimitException,
    AIServiceException,
    AITimeoutException,
)
from app.api.dependencies import get_copilot_conversation_service, get_current_user
from app.models.auth import User
from app.schemas.copilot import (
    CopilotArchiveResponse,
    CopilotChatRequest,
    CopilotConversationCreateRequest,
    CopilotConversationDetailResponse,
    CopilotConversationListResponse,
    CopilotConversationRenameRequest,
    CopilotConversationResponse,
    CopilotTurnResult,
)
if TYPE_CHECKING:
    from app.services.copilot_conversation_service import CopilotConversationService

logger = logging.getLogger("productmind.api.copilot")

router = APIRouter(prefix="/copilot", tags=["Copilot"])


def _map_ai_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, AIAuthenticationException):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream AI provider authentication failed. Please verify provider configuration.",
        )
    if isinstance(exc, AIRateLimitException):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Copilot is temporarily unavailable because the AI service has reached its request limit. Please try again later.",
        )
    if isinstance(exc, AITimeoutException):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Copilot request timed out. Please try again.",
        )
    if isinstance(exc, AIConfigurationException):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured.",
        )
    if isinstance(exc, (AIProviderException, AIServiceException)):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI upstream service encountered an error. Please try again shortly.",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected error processing Copilot request.",
    )


@router.post("/chat", response_model=CopilotTurnResult)
async def send_copilot_message(
    payload: CopilotChatRequest,
    current_user: User = Depends(get_current_user),
    service: "CopilotConversationService" = Depends(get_copilot_conversation_service),
):
    """Send a message to the workspace-aware Product Copilot and persist the turn in Atlas."""
    try:
        return await service.send_message(
            workspace_id=payload.workspace_id,
            user=current_user,
            content=payload.message,
            conversation_id=payload.conversation_id,
            request_id=payload.request_id,
        )
    except HTTPException:
        raise
    except AIServiceException as exc:
        logger.warning("Copilot AI error: %s", type(exc).__name__)
        raise _map_ai_exception(exc)
    except Exception as exc:
        logger.exception("Unhandled error in POST /copilot/chat")
        raise _map_ai_exception(exc)


@router.get("/conversations", response_model=CopilotConversationListResponse)
async def list_copilot_conversations(
    workspaceId: str = Query(..., min_length=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    includeArchived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    service: "CopilotConversationService" = Depends(get_copilot_conversation_service),
):
    """List the authenticated user's conversations in the authorized workspace."""
    conversations, total = await service.list_conversations(
        workspace_id=workspaceId,
        user=current_user,
        skip=skip,
        limit=limit,
        include_archived=includeArchived,
    )
    return CopilotConversationListResponse(
        conversations=conversations,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/conversations",
    response_model=CopilotConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_copilot_conversation(
    payload: CopilotConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    service: "CopilotConversationService" = Depends(get_copilot_conversation_service),
):
    """Create a new empty Copilot conversation in Atlas without calling Groq."""
    return await service.create_conversation(
        workspace_id=payload.workspace_id,
        user=current_user,
        title=payload.title,
        request_id=payload.request_id,
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=CopilotConversationDetailResponse,
)
async def get_copilot_conversation(
    conversation_id: str,
    workspaceId: str = Query(..., min_length=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: "CopilotConversationService" = Depends(get_copilot_conversation_service),
):
    """Retrieve conversation metadata and paginated chronological messages."""
    conversation, messages, total = await service.get_conversation_messages(
        workspace_id=workspaceId,
        user=current_user,
        conversation_id=conversation_id,
        skip=skip,
        limit=limit,
    )
    return CopilotConversationDetailResponse(
        conversation=conversation,
        messages=messages,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=CopilotConversationResponse,
)
async def rename_copilot_conversation(
    conversation_id: str,
    payload: CopilotConversationRenameRequest,
    current_user: User = Depends(get_current_user),
    service: "CopilotConversationService" = Depends(get_copilot_conversation_service),
):
    """Rename a Copilot conversation owned by the authenticated user."""
    from app.services.copilot_conversation_service import _to_conversation_response
    workspace = await service._authorize_workspace(payload.workspace_id, current_user)
    from bson import ObjectId

    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation ID format",
        )
    updated = await service.conversation_repo.update_title(
        conversation_id=conversation_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
        title=payload.title.strip(),
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return _to_conversation_response(updated)


@router.delete(
    "/conversations/{conversation_id}",
    response_model=CopilotArchiveResponse,
)
async def archive_copilot_conversation(
    conversation_id: str,
    workspaceId: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    service: "CopilotConversationService" = Depends(get_copilot_conversation_service),
):
    """Archive a Copilot conversation (soft delete preserving Atlas history)."""
    archived = await service.archive_conversation(
        workspace_id=workspaceId,
        user=current_user,
        conversation_id=conversation_id,
    )
    return CopilotArchiveResponse(
        success=True,
        conversationId=archived.id,
        isArchived=archived.is_archived,
    )

