"""Phase 4.4 tests for CopilotConversationService and Copilot repositories."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.ai.exceptions import (
    AIAuthenticationException,
    AIProviderException,
    AIRateLimitException,
    AITimeoutException,
)
from app.core.enums import CopilotRole, MembershipStatus, PlatformRole, UserRole
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.copilot import CopilotConversation, CopilotMessage
from app.repositories.copilot_repository import (
    CopilotConversationRepository,
    CopilotMessageRepository,
)
from app.services.copilot_ai_service import CopilotAIResponse, CopilotEvidenceItem
from app.services.copilot_conversation_service import (
    CopilotConversationService,
    generate_conversation_title,
)


def _make_user(uid: Optional[ObjectId] = None, email: str = "pm@example.com") -> User:
    return User(
        _id=uid or ObjectId(),
        name="PM User",
        email=email,
        passwordHash="hashed_pw",
        platformRole=PlatformRole.USER,
        isActive=True,
    )


def _make_ws(ws_id: ObjectId, owner_id: ObjectId, name: str = "Apex WS") -> Workspace:
    return Workspace(_id=ws_id, name=name, slug=name.lower().replace(" ", "-"), ownerId=owner_id)


class InMemoryCopilotConversationRepo:
    def __init__(self):
        self.docs: List[CopilotConversation] = []

    async def create_conversation(self, workspace_id, user_id, title="Strategy Session", request_id=None):
        if request_id:
            existing = await self.find_by_request_id(workspace_id, user_id, request_id)
            if existing:
                return existing
        now = datetime.now(timezone.utc)
        conv = CopilotConversation(
            _id=ObjectId(),
            workspaceId=workspace_id,
            userId=user_id,
            title=title[:150],
            requestId=request_id,
            isArchived=False,
            messageCount=0,
            lastMessageAt=now,
            createdAt=now,
            updatedAt=now,
        )
        self.docs.append(conv)
        return conv

    async def find_by_request_id(self, workspace_id, user_id, request_id):
        for c in self.docs:
            if c.workspace_id == workspace_id and c.user_id == user_id and c.request_id == request_id:
                return c
        return None

    async def find_by_id_and_owner(self, conversation_id, workspace_id, user_id):
        cid = ObjectId(conversation_id) if isinstance(conversation_id, str) else conversation_id
        for c in self.docs:
            if c.id == cid and c.workspace_id == workspace_id and c.user_id == user_id:
                return c
        return None

    async def find_user_conversations(self, workspace_id, user_id, limit=20, skip=0, include_archived=False):
        items = [
            c
            for c in self.docs
            if c.workspace_id == workspace_id
            and c.user_id == user_id
            and (include_archived or not c.is_archived)
        ]
        items.sort(key=lambda c: c.last_message_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return items[skip : skip + limit]

    async def count_user_conversations(self, workspace_id, user_id, include_archived=False):
        return len(
            [
                c
                for c in self.docs
                if c.workspace_id == workspace_id
                and c.user_id == user_id
                and (include_archived or not c.is_archived)
            ]
        )

    async def update_activity(self, conversation_id, workspace_id, user_id, last_message_at=None, increment_messages=0):
        conv = await self.find_by_id_and_owner(conversation_id, workspace_id, user_id)
        if not conv:
            return None
        conv.last_message_at = last_message_at or datetime.now(timezone.utc)
        conv.message_count += increment_messages
        conv.updated_at = datetime.now(timezone.utc)
        return conv

    async def archive_conversation(self, conversation_id, workspace_id, user_id):
        conv = await self.find_by_id_and_owner(conversation_id, workspace_id, user_id)
        if not conv:
            return None
        conv.is_archived = True
        return conv

    async def update_title(self, conversation_id, workspace_id, user_id, title):
        conv = await self.find_by_id_and_owner(conversation_id, workspace_id, user_id)
        if not conv:
            return None
        conv.title = title[:150]
        return conv


class InMemoryCopilotMessageRepo:
    def __init__(self):
        self.docs: List[CopilotMessage] = []
        self.last_queries: List[Dict[str, Any]] = []

    async def create_message(self, message: CopilotMessage):
        if message.id is None:
            message.id = ObjectId()
        if message.created_at is None:
            message.created_at = datetime.now(timezone.utc)
        self.docs.append(message)
        return message

    async def find_by_conversation(self, conversation_id, workspace_id, limit=100, skip=0, ascending=True):
        self.last_queries.append({"op": "find_by_conversation", "conversationId": conversation_id, "workspaceId": workspace_id})
        items = [m for m in self.docs if m.conversation_id == conversation_id and m.workspace_id == workspace_id]
        items.sort(key=lambda m: (m.created_at or datetime.min.replace(tzinfo=timezone.utc), str(m.id)), reverse=not ascending)
        return items[skip : skip + limit]

    async def find_recent_for_history(self, conversation_id, workspace_id, limit=10):
        self.last_queries.append({"op": "find_recent_for_history", "conversationId": conversation_id, "workspaceId": workspace_id})
        items = [
            m
            for m in self.docs
            if m.conversation_id == conversation_id
            and m.workspace_id == workspace_id
            and m.role in (CopilotRole.USER, CopilotRole.ASSISTANT)
            and m.status not in ("failed", "pending")
        ]
        items.sort(key=lambda m: (m.created_at or datetime.min.replace(tzinfo=timezone.utc), str(m.id)))
        return items[-limit:]

    async def count_by_conversation(self, conversation_id, workspace_id):
        return len([m for m in self.docs if m.conversation_id == conversation_id and m.workspace_id == workspace_id])

    async def find_by_request_id(self, conversation_id, workspace_id, role, request_id):
        for m in self.docs:
            if (
                m.conversation_id == conversation_id
                and m.workspace_id == workspace_id
                and m.role == role
                and m.request_id == request_id
            ):
                return m
        return None

    async def update_message_result(self, message_id, conversation_id, workspace_id, update_fields):
        for m in self.docs:
            if m.id == message_id and m.conversation_id == conversation_id and m.workspace_id == workspace_id:
                if "content" in update_fields:
                    m.content = update_fields["content"]
                if "status" in update_fields:
                    m.status = update_fields["status"]
                if "errorMessage" in update_fields:
                    m.error_message = update_fields["errorMessage"]
                if "evidence" in update_fields:
                    from app.models.copilot import CopilotEvidence
                    m.evidence = [CopilotEvidence(**e) for e in update_fields["evidence"]]
                if "modelInfo" in update_fields:
                    from app.models.copilot import CopilotModelInfo
                    m.model_info = CopilotModelInfo(**update_fields["modelInfo"])
                return m
        return None


def _build_service(workspaces: Dict[ObjectId, Workspace], memberships: Dict[tuple, WorkspaceMembership], ai_mock):
    ws_repo = MagicMock(find_by_id=AsyncMock(side_effect=lambda wid: workspaces.get(ObjectId(wid) if isinstance(wid, str) else wid)))
    mem_repo = MagicMock(find_membership=AsyncMock(side_effect=lambda wid, uid: memberships.get((wid, uid))))
    conv_repo = InMemoryCopilotConversationRepo()
    msg_repo = InMemoryCopilotMessageRepo()
    svc = CopilotConversationService(
        workspace_repo=ws_repo,
        membership_repo=mem_repo,
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        copilot_ai_service=ai_mock,
    )
    return svc, conv_repo, msg_repo


def _ai_response(answer: str = "Top complaint is slow CSV export.") -> CopilotAIResponse:
    return CopilotAIResponse(
        answer=answer,
        provider="groq",
        modelName="qwen/qwen3.8-27b",
        inputTokens=410,
        outputTokens=65,
        totalTokens=475,
        evidence=[CopilotEvidenceItem(type="feedback", label="Workspace Feedback (20 items)", path="/feedback", count=20)],
        contextMetadata={"orderedDomains": ["feedback"]},
    )


def test_deterministic_title_generation():
    short = generate_conversation_title("   Summarize   latest   feedback   ")
    assert short == "Summarize latest feedback"
    long_q = "Why did Async Bulk Export receive a priority score of 85 compared to mobile offline mode and billing?"
    title = generate_conversation_title(long_q)
    assert len(title) <= 60
    assert title.endswith("...")


@pytest.mark.asyncio
async def test_conversation_creation_persistence_and_idempotency():
    uid = ObjectId()
    ws_id = ObjectId()
    user = _make_user(uid)
    ws = _make_ws(ws_id, uid)
    ai = MagicMock(ask=AsyncMock(return_value=_ai_response()))
    svc, conv_repo, msg_repo = _build_service({ws_id: ws}, {}, ai)

    # First submission creates conversation + user + assistant messages
    turn1 = await svc.send_message(
        workspace_id=str(ws_id),
        user=user,
        content="Summarize latest customer feedback",
        request_id="req-init-1",
    )
    assert turn1.conversation.title == "Summarize latest customer feedback"
    assert turn1.conversation.message_count == 2
    assert turn1.user_message.role == CopilotRole.USER
    assert turn1.assistant_message.status == "completed"
    assert turn1.assistant_message.model_info["provider"] == "groq"
    assert turn1.assistant_message.model_info["modelName"] == "qwen/qwen3.8-27b"
    assert turn1.assistant_message.model_info["tokensUsed"] == 475
    assert turn1.assistant_message.model_info["inputTokens"] == 410
    assert turn1.assistant_message.model_info["outputTokens"] == 65
    assert len(turn1.assistant_message.evidence) == 1
    assert ai.ask.await_count == 1

    # Repeated initial submission with same request_id + conversation_id does NOT duplicate or call Groq
    turn_dup = await svc.send_message(
        workspace_id=str(ws_id),
        user=user,
        content="Summarize latest customer feedback",
        conversation_id=turn1.conversation.id,
        request_id="req-init-1",
    )
    assert turn_dup.assistant_message.id == turn1.assistant_message.id
    assert ai.ask.await_count == 1
    assert len(conv_repo.docs) == 1
    assert len(msg_repo.docs) == 2

    # Listing conversations returns the created conversation
    convs, total = await svc.list_conversations(str(ws_id), user)
    assert total == 1
    assert convs[0].id == turn1.conversation.id


@pytest.mark.asyncio
async def test_failure_handling_preserves_user_message_and_allows_retry():
    uid = ObjectId()
    ws_id = ObjectId()
    user = _make_user(uid)
    ws = _make_ws(ws_id, uid)

    ai = MagicMock(
        ask=AsyncMock(
            side_effect=[
                AIRateLimitException("429 Too Many Requests", provider="groq"),
                AITimeoutException("Timed out", provider="groq"),
                AIAuthenticationException("401 Invalid key", provider="groq"),
                AIProviderException("502 Bad Gateway", provider="groq"),
                _ai_response("Recovered answer after retry."),
            ]
        )
    )
    svc, conv_repo, msg_repo = _build_service({ws_id: ws}, {}, ai)

    # 1. Groq 429 after user message persistence
    with pytest.raises(AIRateLimitException):
        await svc.send_message(str(ws_id), user, "Why did export score 85?", request_id="req-retry-1")

    conv_id = str(conv_repo.docs[0].id)
    assert len(msg_repo.docs) == 2  # 1 user + 1 failed assistant record
    assert msg_repo.docs[0].role == CopilotRole.USER
    assert msg_repo.docs[0].status == "completed"
    assert msg_repo.docs[1].role == CopilotRole.ASSISTANT
    assert msg_repo.docs[1].status == "failed"
    assert msg_repo.docs[1].content == ""

    # 2. Timeout, Auth, Provider errors on new request_ids record failed status without fake answers
    for idx, exc_cls in enumerate((AITimeoutException, AIAuthenticationException, AIProviderException)):
        with pytest.raises(exc_cls):
            await svc.send_message(str(ws_id), user, f"Question {idx}", conversation_id=conv_id, request_id=f"req-err-{idx}")

    # 3. Retry the failed req-retry-1 -> reuses persisted user message, succeeds, updates assistant to completed
    retried = await svc.send_message(
        str(ws_id),
        user,
        "Why did export score 85?",
        conversation_id=conv_id,
        request_id="req-retry-1",
    )
    assert retried.retried is True
    assert retried.assistant_message.status == "completed"
    assert retried.assistant_message.content == "Recovered answer after retry."
    # Only one user message exists for req-retry-1
    req_retry_user_msgs = [m for m in msg_repo.docs if m.request_id == "req-retry-1" and m.role == CopilotRole.USER]
    assert len(req_retry_user_msgs) == 1


@pytest.mark.asyncio
async def test_workspace_and_user_isolation_and_pagination():
    user_a = _make_user(ObjectId(), "a@example.com")
    user_b = _make_user(ObjectId(), "b@example.com")
    ws_a_id, ws_b_id = ObjectId(), ObjectId()
    ws_a = _make_ws(ws_a_id, user_a.id, "WS A")
    ws_b = _make_ws(ws_b_id, user_b.id, "WS B")

    # Add user_b as active member of ws_a to test user-level isolation within same workspace
    memberships = {
        (ws_a_id, user_b.id): WorkspaceMembership(
            workspaceId=ws_a_id,
            userId=user_b.id,
            role=UserRole.PRODUCT_MANAGER,
            status=MembershipStatus.ACTIVE,
        )
    }
    ai = MagicMock(ask=AsyncMock(return_value=_ai_response("Answer")))
    svc, conv_repo, msg_repo = _build_service({ws_a_id: ws_a, ws_b_id: ws_b}, memberships, ai)

    t1 = await svc.send_message(str(ws_a_id), user_a, "Turn 1")
    await svc.send_message(str(ws_a_id), user_a, "Turn 2", conversation_id=t1.conversation.id)
    await svc.send_message(str(ws_a_id), user_a, "Turn 3", conversation_id=t1.conversation.id)

    # User B cannot access User A's conversation or archive it
    with pytest.raises(HTTPException) as exc_get:
        await svc.get_conversation_messages(str(ws_a_id), user_b, t1.conversation.id)
    assert exc_get.value.status_code == 404

    with pytest.raises(HTTPException) as exc_arch:
        await svc.archive_conversation(str(ws_a_id), user_b, t1.conversation.id)
    assert exc_arch.value.status_code == 404

    # Workspace B owner cannot access Workspace A conversation
    with pytest.raises(HTTPException):
        await svc.get_conversation_messages(str(ws_b_id), user_b, t1.conversation.id)

    # Pagination preserves chronological order across pages
    _, page1, total = await svc.get_conversation_messages(str(ws_a_id), user_a, t1.conversation.id, skip=0, limit=2)
    _, page2, _ = await svc.get_conversation_messages(str(ws_a_id), user_a, t1.conversation.id, skip=2, limit=2)
    assert total == 6
    assert len(page1) == 2 and len(page2) == 2
    assert page1[0].content == "Turn 1"
    assert page2[0].content == "Turn 2"

    # Verify all message queries included workspaceId
    assert all(q["workspaceId"] == ws_a_id for q in msg_repo.last_queries)


@pytest.mark.asyncio
async def test_live_atlas_persistence_survives_restart(async_db):
    """
    Controlled live MongoDB Atlas test: creates a synthetic conversation + turn,
    re-instantiates repositories/service (simulating backend restart), verifies
    persistence & workspace isolation, and cleans up ONLY the synthetic records.
    """
    ws_id = ObjectId()
    user_id = ObjectId()
    other_ws_id = ObjectId()
    user = _make_user(user_id, "atlas-test@example.com")
    ws = _make_ws(ws_id, user_id, "Atlas Copilot Test WS")
    other_ws = _make_ws(other_ws_id, user_id, "Other WS")

    ws_repo = MagicMock(find_by_id=AsyncMock(side_effect=lambda wid: ws if ObjectId(wid) == ws_id else other_ws))
    mem_repo = MagicMock(find_membership=AsyncMock(return_value=None))
    ai_mock = MagicMock(ask=AsyncMock(return_value=_ai_response("Persisted Atlas reply.")))

    conv_id: Optional[ObjectId] = None
    try:
        # Process 1: create & persist
        svc1 = CopilotConversationService(
            workspace_repo=ws_repo,
            membership_repo=mem_repo,
            conversation_repo=CopilotConversationRepository(async_db),
            message_repo=CopilotMessageRepository(async_db),
            copilot_ai_service=ai_mock,
        )
        turn = await svc1.send_message(
            workspace_id=str(ws_id),
            user=user,
            content="Persist this message in MongoDB Atlas",
            request_id=f"atlas-live-{ObjectId()}",
        )
        conv_id = ObjectId(turn.conversation.id)

        # Process 2 (simulated restart): fresh repositories & service instance
        svc2 = CopilotConversationService(
            workspace_repo=ws_repo,
            membership_repo=mem_repo,
            conversation_repo=CopilotConversationRepository(async_db),
            message_repo=CopilotMessageRepository(async_db),
            copilot_ai_service=ai_mock,
        )
        conv, msgs, total = await svc2.get_conversation_messages(str(ws_id), user, str(conv_id))
        assert total == 2
        assert conv.title == "Persist this message in MongoDB Atlas"
        assert msgs[0].role == CopilotRole.USER
        assert msgs[1].role == CopilotRole.ASSISTANT
        assert msgs[1].content == "Persisted Atlas reply."

        # Cross-workspace isolation on real Atlas
        with pytest.raises(HTTPException) as exc_iso:
            await svc2.get_conversation_messages(str(other_ws_id), user, str(conv_id))
        assert exc_iso.value.status_code == 404
    finally:
        if conv_id is not None:
            await async_db["copilot_messages"].delete_many({"conversationId": conv_id, "workspaceId": ws_id})
            await async_db["copilot_conversations"].delete_one({"_id": conv_id, "workspaceId": ws_id})
