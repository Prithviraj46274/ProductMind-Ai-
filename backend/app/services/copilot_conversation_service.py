"""
ProductMind AI — Phase 4.4: Conversation Persistence Service
Orchestrates workspace-authorized, user-scoped conversation and message
persistence in MongoDB Atlas around Phase 4.3 CopilotAIService.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from fastapi import HTTPException, status

from app.ai.exceptions import (
    AIAuthenticationException,
    AIConfigurationException,
    AIProviderException,
    AIRateLimitException,
    AIServiceException,
    AITimeoutException,
)
from app.core.enums import CopilotRole, MembershipStatus, PlatformRole
from app.models.auth import User, Workspace
from app.models.copilot import (
    CopilotConversation,
    CopilotEvidence,
    CopilotMessage,
    CopilotModelInfo,
)
from app.repositories import (
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.repositories.base import DuplicateEntityError
from app.repositories.copilot_repository import (
    CopilotConversationRepository,
    CopilotMessageRepository,
)
from app.schemas.copilot import (
    CopilotConversationResponse,
    CopilotMessageResponse,
    CopilotTurnResult,
)
from app.services.copilot_ai_service import CopilotAIService

logger = logging.getLogger("productmind.copilot.persistence")

MAX_TITLE_CHARS = 60
MAX_HISTORY_FOR_AI = 10


def generate_conversation_title(first_message: str, max_len: int = MAX_TITLE_CHARS) -> str:
    """Deterministically builds a readable title from the initial user message without an LLM call."""
    cleaned = " ".join((first_message or "").split())
    if not cleaned:
        return "Strategy Session"
    if len(cleaned) <= max_len:
        return cleaned
    truncated = cleaned[: max(1, max_len - 3)].rstrip()
    # Avoid cutting mid-word when possible
    if " " in truncated and len(truncated) > 20:
        truncated = truncated.rsplit(" ", 1)[0].rstrip()
    return f"{truncated}..."


def _sanitize_error_message(exc: Exception) -> str:
    if isinstance(exc, AIRateLimitException):
        return "AI rate limit or free-tier quota temporarily exceeded."
    if isinstance(exc, AITimeoutException):
        return "AI model request timed out."
    if isinstance(exc, AIAuthenticationException):
        return "AI provider authentication failed."
    if isinstance(exc, AIConfigurationException):
        return "AI provider configuration error."
    if isinstance(exc, AIProviderException):
        return "AI upstream service error."
    if isinstance(exc, AIServiceException):
        return "AI response generation failed."
    return f"Unexpected generation error ({type(exc).__name__})."


def _to_conversation_response(conv: CopilotConversation) -> CopilotConversationResponse:
    return CopilotConversationResponse(
        id=str(conv.id),
        workspaceId=str(conv.workspace_id),
        userId=str(conv.user_id),
        title=conv.title,
        isArchived=conv.is_archived,
        messageCount=conv.message_count,
        lastMessageAt=conv.last_message_at,
        createdAt=conv.created_at,
    )


def _to_message_response(msg: CopilotMessage) -> CopilotMessageResponse:
    return CopilotMessageResponse(
        id=str(msg.id),
        conversationId=str(msg.conversation_id),
        role=msg.role,
        content=msg.content,
        status=msg.status,
        requestId=msg.request_id,
        errorMessage=msg.error_message,
        evidence=[ev.model_dump(by_alias=True) for ev in (msg.evidence or [])],
        modelInfo=msg.model_info.model_dump(by_alias=True) if msg.model_info else {},
        createdAt=msg.created_at,
    )


class CopilotConversationService:
    """
    Persists Copilot conversations and messages in MongoDB Atlas with strict
    workspace + user isolation, idempotent request handling, and safe failure recording.
    """

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        membership_repo: WorkspaceMembershipRepository,
        conversation_repo: CopilotConversationRepository,
        message_repo: CopilotMessageRepository,
        copilot_ai_service: CopilotAIService,
    ):
        self.workspace_repo = workspace_repo
        self.membership_repo = membership_repo
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.copilot_ai_service = copilot_ai_service

    async def _authorize_workspace(self, workspace_id: str, user: User) -> Workspace:
        if not ObjectId.is_valid(workspace_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid workspace ID format",
            )
        workspace = await self.workspace_repo.find_by_id(workspace_id)
        if not workspace or not workspace.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )
        is_owner = workspace.owner_id == user.id
        is_platform_admin = user.platform_role == PlatformRole.PLATFORM_ADMIN
        if not (is_owner or is_platform_admin):
            membership = await self.membership_repo.find_membership(workspace.id, user.id)
            if not membership or membership.status != MembershipStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to this workspace",
                )
        return workspace

    async def create_conversation(
        self,
        workspace_id: str,
        user: User,
        title: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> CopilotConversationResponse:
        workspace = await self._authorize_workspace(workspace_id, user)
        conv = await self.conversation_repo.create_conversation(
            workspace_id=workspace.id,
            user_id=user.id,
            title=title or "Strategy Session",
            request_id=request_id,
        )
        return _to_conversation_response(conv)

    async def list_conversations(
        self,
        workspace_id: str,
        user: User,
        skip: int = 0,
        limit: int = 20,
        include_archived: bool = False,
    ) -> Tuple[List[CopilotConversationResponse], int]:
        workspace = await self._authorize_workspace(workspace_id, user)
        bounded_limit = max(1, min(100, int(limit)))
        bounded_skip = max(0, int(skip))
        items = await self.conversation_repo.find_user_conversations(
            workspace_id=workspace.id,
            user_id=user.id,
            limit=bounded_limit,
            skip=bounded_skip,
            include_archived=include_archived,
        )
        total = await self.conversation_repo.count_user_conversations(
            workspace_id=workspace.id,
            user_id=user.id,
            include_archived=include_archived,
        )
        return [_to_conversation_response(c) for c in items], total

    async def get_conversation_messages(
        self,
        workspace_id: str,
        user: User,
        conversation_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[CopilotConversationResponse, List[CopilotMessageResponse], int]:
        workspace = await self._authorize_workspace(workspace_id, user)
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID format",
            )
        conv = await self.conversation_repo.find_by_id_and_owner(
            conversation_id=conversation_id,
            workspace_id=workspace.id,
            user_id=user.id,
        )
        if not conv or not conv.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        bounded_limit = max(1, min(100, int(limit)))
        bounded_skip = max(0, int(skip))
        messages = await self.message_repo.find_by_conversation(
            conversation_id=conv.id,
            workspace_id=workspace.id,
            limit=bounded_limit,
            skip=bounded_skip,
            ascending=True,
        )
        total = await self.message_repo.count_by_conversation(
            conversation_id=conv.id,
            workspace_id=workspace.id,
        )
        return _to_conversation_response(conv), [_to_message_response(m) for m in messages], total

    async def archive_conversation(
        self,
        workspace_id: str,
        user: User,
        conversation_id: str,
    ) -> CopilotConversationResponse:
        workspace = await self._authorize_workspace(workspace_id, user)
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid conversation ID format",
            )
        archived = await self.conversation_repo.archive_conversation(
            conversation_id=conversation_id,
            workspace_id=workspace.id,
            user_id=user.id,
        )
        if not archived:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return _to_conversation_response(archived)

    async def send_message(
        self,
        workspace_id: str,
        user: User,
        content: str,
        conversation_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> CopilotTurnResult:
        """
        Persists the user message, loads bounded chronological history, invokes
        Phase 4.3 CopilotAIService, and persists either the completed assistant
        response or a failed-generation record without losing the user message.
        """
        clean_content = (content or "").strip()
        if not clean_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message content cannot be empty.",
            )

        workspace = await self._authorize_workspace(workspace_id, user)
        ws_oid = workspace.id

        # Step 1: Create or retrieve & validate conversation ownership
        if conversation_id:
            if not ObjectId.is_valid(conversation_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid conversation ID format",
                )
            conv = await self.conversation_repo.find_by_id_and_owner(
                conversation_id=conversation_id,
                workspace_id=ws_oid,
                user_id=user.id,
            )
            if not conv or not conv.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found",
                )
        else:
            conv = await self.conversation_repo.create_conversation(
                workspace_id=ws_oid,
                user_id=user.id,
                title=generate_conversation_title(clean_content),
                request_id=request_id,
            )

        conv_oid = conv.id

        # Step 2: Idempotency check on completed or previously failed assistant response
        existing_assistant: Optional[CopilotMessage] = None
        existing_user: Optional[CopilotMessage] = None
        retried = False

        if request_id:
            existing_assistant = await self.message_repo.find_by_request_id(
                conversation_id=conv_oid,
                workspace_id=ws_oid,
                role=CopilotRole.ASSISTANT,
                request_id=request_id,
            )
            existing_user = await self.message_repo.find_by_request_id(
                conversation_id=conv_oid,
                workspace_id=ws_oid,
                role=CopilotRole.USER,
                request_id=request_id,
            )
            if existing_assistant is not None and existing_assistant.status == "completed":
                if existing_user is None:
                    # Fallback if user message had no request_id
                    recent = await self.message_repo.find_by_conversation(
                        conversation_id=conv_oid,
                        workspace_id=ws_oid,
                        limit=2,
                        ascending=False,
                    )
                    existing_user = next(
                        (m for m in recent if m.role == CopilotRole.USER),
                        existing_assistant,
                    )
                return CopilotTurnResult(
                    conversation=_to_conversation_response(conv),
                    userMessage=_to_message_response(existing_user),
                    assistantMessage=_to_message_response(existing_assistant),
                    retried=False,
                )
            if existing_assistant is not None and existing_assistant.status == "failed":
                retried = True

        # Step 3: Persist user message (unless already persisted on a retry/duplicate requestId)
        now = datetime.now(timezone.utc)
        user_msg = existing_user
        user_msg_created_now = False
        if user_msg is None:
            new_user_msg = CopilotMessage(
                workspaceId=ws_oid,
                conversationId=conv_oid,
                requestId=request_id,
                role=CopilotRole.USER,
                content=clean_content,
                status="completed",
                createdAt=now,
                updatedAt=now,
            )
            try:
                user_msg = await self.message_repo.create_message(new_user_msg)
                user_msg_created_now = True
            except DuplicateEntityError:
                if request_id:
                    user_msg = await self.message_repo.find_by_request_id(
                        conversation_id=conv_oid,
                        workspace_id=ws_oid,
                        role=CopilotRole.USER,
                        request_id=request_id,
                    )
                if user_msg is None:
                    raise

        if user_msg_created_now:
            updated_conv = await self.conversation_repo.update_activity(
                conversation_id=conv_oid,
                workspace_id=ws_oid,
                user_id=user.id,
                last_message_at=now,
                increment_messages=1,
            )
            if updated_conv is not None:
                conv = updated_conv

        # Step 4: Load bounded chronological history (excluding failed/pending & current user turn)
        recent_msgs = await self.message_repo.find_recent_for_history(
            conversation_id=conv_oid,
            workspace_id=ws_oid,
            limit=MAX_HISTORY_FOR_AI,
        )
        history_payload: List[Dict[str, Any]] = [
            {
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "content": m.content,
                "workspaceId": str(ws_oid),
            }
            for m in recent_msgs
            if m.id != user_msg.id
        ]

        # Step 5: Invoke Phase 4.3 CopilotAIService
        try:
            ai_result = await self.copilot_ai_service.ask(
                workspace_id=str(ws_oid),
                user=user,
                question=clean_content,
                conversation_history=history_payload,
            )
        except Exception as exc:
            err_msg = _sanitize_error_message(exc)
            fail_now = datetime.now(timezone.utc)
            if existing_assistant is not None and existing_assistant.id is not None:
                await self.message_repo.update_message_result(
                    message_id=existing_assistant.id,
                    conversation_id=conv_oid,
                    workspace_id=ws_oid,
                    update_fields={
                        "status": "failed",
                        "content": "",
                        "errorMessage": err_msg,
                    },
                )
            else:
                failed_assistant = CopilotMessage(
                    workspaceId=ws_oid,
                    conversationId=conv_oid,
                    requestId=request_id,
                    role=CopilotRole.ASSISTANT,
                    content="",
                    status="failed",
                    errorMessage=err_msg,
                    createdAt=fail_now,
                    updatedAt=fail_now,
                )
                try:
                    await self.message_repo.create_message(failed_assistant)
                except DuplicateEntityError:
                    logger.warning("Duplicate failed assistant record for request_id=%s", request_id)
            await self.conversation_repo.update_activity(
                conversation_id=conv_oid,
                workspace_id=ws_oid,
                user_id=user.id,
                last_message_at=fail_now,
                increment_messages=0,
            )
            raise

        # Step 6: Persist completed assistant response & update conversation metadata
        done_now = datetime.now(timezone.utc)
        evidence_models = [
            CopilotEvidence(
                type=ev.type,
                label=ev.label,
                path=ev.path,
                count=ev.count,
                entityId=ev.entity_id,
            )
            for ev in (ai_result.evidence or [])
        ]
        model_info = CopilotModelInfo(
            provider=ai_result.provider,
            modelName=ai_result.model_name,
            tokensUsed=ai_result.total_tokens or 0,
            inputTokens=ai_result.input_tokens,
            outputTokens=ai_result.output_tokens,
        )

        if existing_assistant is not None and existing_assistant.id is not None:
            assistant_msg = await self.message_repo.update_message_result(
                message_id=existing_assistant.id,
                conversation_id=conv_oid,
                workspace_id=ws_oid,
                update_fields={
                    "content": ai_result.answer,
                    "status": "completed",
                    "errorMessage": None,
                    "evidence": [ev.model_dump(by_alias=True) for ev in evidence_models],
                    "modelInfo": model_info.model_dump(by_alias=True),
                },
            )
        else:
            new_assistant = CopilotMessage(
                workspaceId=ws_oid,
                conversationId=conv_oid,
                requestId=request_id,
                role=CopilotRole.ASSISTANT,
                content=ai_result.answer,
                status="completed",
                evidence=evidence_models,
                modelInfo=model_info,
                createdAt=done_now,
                updatedAt=done_now,
            )
            assistant_msg = await self.message_repo.create_message(new_assistant)

        updated_conv = await self.conversation_repo.update_activity(
            conversation_id=conv_oid,
            workspace_id=ws_oid,
            user_id=user.id,
            last_message_at=done_now,
            increment_messages=1,
        )
        if updated_conv is not None:
            conv = updated_conv

        return CopilotTurnResult(
            conversation=_to_conversation_response(conv),
            userMessage=_to_message_response(user_msg),
            assistantMessage=_to_message_response(assistant_msg),
            retried=retried,
        )
