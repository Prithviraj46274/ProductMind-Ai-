"""Phase 4.5 tests for Copilot FastAPI REST API endpoints (/api/v1/copilot/*)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from app.ai.exceptions import AIAuthenticationException, AIRateLimitException, AITimeoutException
from app.api.dependencies import get_copilot_conversation_service, get_current_user, get_mongo_db
from app.core.enums import CopilotRole, PlatformRole
from app.main import app
from app.models.auth import User, Workspace
from app.services.copilot_ai_service import CopilotAIResponse, CopilotEvidenceItem
from app.services.copilot_conversation_service import CopilotConversationService
from tests.api.test_copilot_conversation_service import (
    InMemoryCopilotConversationRepo,
    InMemoryCopilotMessageRepo,
)


def _make_user(uid: ObjectId | None = None, email: str = "pm@example.com") -> User:
    return User(
        _id=uid or ObjectId(),
        name="PM Tester",
        email=email,
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )


def _setup_app(user: User, ws_id: ObjectId, ai_mock):
    ws = Workspace(_id=ws_id, name="Apex WS", slug="apex-ws", ownerId=user.id)
    ws_repo = MagicMock(
        find_by_id=AsyncMock(side_effect=lambda wid: ws if ObjectId(wid) == ws_id else None)
    )
    mem_repo = MagicMock(find_membership=AsyncMock(return_value=None))
    conv_repo = InMemoryCopilotConversationRepo()
    msg_repo = InMemoryCopilotMessageRepo()

    svc = CopilotConversationService(
        workspace_repo=ws_repo,
        membership_repo=mem_repo,
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        copilot_ai_service=ai_mock,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_copilot_conversation_service] = lambda: svc
    return svc


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_copilot_endpoints_full_lifecycle_and_idempotency():
    user = _make_user()
    ws_id = ObjectId()
    ai_res = CopilotAIResponse(
        answer="Top complaint is slow CSV export.",
        provider="groq",
        modelName="qwen/qwen3.8-27b",
        inputTokens=300,
        outputTokens=45,
        totalTokens=345,
        evidence=[CopilotEvidenceItem(type="feedback", label="Feedback (20)", path="/feedback", count=20)],
        contextMetadata={},
    )
    ai_mock = MagicMock(ask=AsyncMock(return_value=ai_res))
    _setup_app(user, ws_id, ai_mock)

    client = TestClient(app)

    # 1. Create empty conversation -> 201, zero AI calls
    r_create = client.post(
        "/api/v1/copilot/conversations",
        json={"workspaceId": str(ws_id), "title": "Q4 Review", "requestId": "create-1"},
    )
    assert r_create.status_code == 201
    conv_id = r_create.json()["id"]
    assert ai_mock.ask.await_count == 0

    # 2. Send chat message -> 200
    r_chat = client.post(
        "/api/v1/copilot/chat",
        json={
            "workspaceId": str(ws_id),
            "conversationId": conv_id,
            "message": "What are top complaints?",
            "requestId": "req-1",
        },
    )
    assert r_chat.status_code == 200
    body = r_chat.json()
    assert body["assistantMessage"]["content"] == "Top complaint is slow CSV export."
    assert body["assistantMessage"]["evidence"][0]["path"] == "/feedback"
    assert ai_mock.ask.await_count == 1

    # 3. Idempotent replay -> 200, no second Groq call
    r_replay = client.post(
        "/api/v1/copilot/chat",
        json={
            "workspaceId": str(ws_id),
            "conversationId": conv_id,
            "message": "What are top complaints?",
            "requestId": "req-1",
        },
    )
    assert r_replay.status_code == 200
    assert r_replay.json()["assistantMessage"]["id"] == body["assistantMessage"]["id"]
    assert ai_mock.ask.await_count == 1

    # 4. List conversations -> 200
    r_list = client.get(f"/api/v1/copilot/conversations?workspaceId={ws_id}")
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 1

    # 5. Get conversation messages with pagination -> 200
    r_get = client.get(f"/api/v1/copilot/conversations/{conv_id}?workspaceId={ws_id}&skip=0&limit=10")
    assert r_get.status_code == 200
    assert r_get.json()["total"] == 2
    assert len(r_get.json()["messages"]) == 2

    # 6. Rename conversation -> 200
    r_patch = client.patch(
        f"/api/v1/copilot/conversations/{conv_id}",
        json={"workspaceId": str(ws_id), "title": "Renamed Session"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["title"] == "Renamed Session"

    # 7. Archive conversation -> 200 and excluded from active list
    r_del = client.delete(f"/api/v1/copilot/conversations/{conv_id}?workspaceId={ws_id}")
    assert r_del.status_code == 200
    assert r_del.json()["isArchived"] is True

    r_list_after = client.get(f"/api/v1/copilot/conversations?workspaceId={ws_id}")
    assert r_list_after.json()["total"] == 0


def test_copilot_endpoints_error_mapping_and_validation():
    user = _make_user()
    ws_id = ObjectId()
    ai_mock = MagicMock(
        ask=AsyncMock(
            side_effect=[
                AIRateLimitException("429 Too Many Requests", provider="groq"),
                AITimeoutException("Timeout", provider="groq"),
                AIAuthenticationException("Upstream Groq key rejected", provider="groq"),
            ]
        )
    )
    _setup_app(user, ws_id, ai_mock)
    client = TestClient(app)

    # Empty message -> 400
    r_empty = client.post(
        "/api/v1/copilot/chat",
        json={"workspaceId": str(ws_id), "message": "   "},
    )
    assert r_empty.status_code == 400

    # Invalid conversationId -> 400
    r_bad_id = client.get(f"/api/v1/copilot/conversations/not-an-oid?workspaceId={ws_id}")
    assert r_bad_id.status_code == 400

    # Unauthorized / unknown workspace -> 404
    r_other_ws = client.get(f"/api/v1/copilot/conversations?workspaceId={ObjectId()}")
    assert r_other_ws.status_code == 404

    # Groq 429 -> 429
    r_429 = client.post(
        "/api/v1/copilot/chat",
        json={"workspaceId": str(ws_id), "message": "Hello", "requestId": "req-429"},
    )
    assert r_429.status_code == 429

    # Groq timeout -> 504
    r_504 = client.post(
        "/api/v1/copilot/chat",
        json={"workspaceId": str(ws_id), "message": "Hello", "requestId": "req-504"},
    )
    assert r_504.status_code == 504

    # Upstream Groq auth failure -> 502 (NOT 401!)
    r_groq_auth = client.post(
        "/api/v1/copilot/chat",
        json={"workspaceId": str(ws_id), "message": "Hello", "requestId": "req-502"},
    )
    assert r_groq_auth.status_code == 502


def test_copilot_endpoints_require_authentication():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_mongo_db] = lambda: MagicMock()
    client = TestClient(app)
    r = client.get(f"/api/v1/copilot/conversations?workspaceId={ObjectId()}")
    assert r.status_code == 401


def test_copilot_two_user_two_workspace_isolation_and_secret_safety():
    user_a = _make_user(ObjectId(), "alice@example.com")
    user_b = _make_user(ObjectId(), "bob@example.com")
    ws_a_id = ObjectId()
    ws_b_id = ObjectId()
    ws_a = Workspace(_id=ws_a_id, name="WS A", slug="ws-a", ownerId=user_a.id)
    ws_b = Workspace(_id=ws_b_id, name="WS B", slug="ws-b", ownerId=user_b.id)

    ws_repo = MagicMock(
        find_by_id=AsyncMock(
            side_effect=lambda wid: ws_a if ObjectId(wid) == ws_a_id else (ws_b if ObjectId(wid) == ws_b_id else None)
        )
    )
    mem_repo = MagicMock(find_membership=AsyncMock(return_value=None))
    conv_repo = InMemoryCopilotConversationRepo()
    msg_repo = InMemoryCopilotMessageRepo()
    ai_res = CopilotAIResponse(
        answer="Direct Answer: WS A confidential summary.",
        provider="groq",
        modelName="qwen/qwen3.8-27b",
        inputTokens=150,
        outputTokens=40,
        totalTokens=190,
        evidence=[],
        contextMetadata={},
    )
    ai_mock = MagicMock(ask=AsyncMock(return_value=ai_res))
    svc = CopilotConversationService(
        workspace_repo=ws_repo,
        membership_repo=mem_repo,
        conversation_repo=conv_repo,
        message_repo=msg_repo,
        copilot_ai_service=ai_mock,
    )

    active_user = {"current": user_a}
    app.dependency_overrides[get_current_user] = lambda: active_user["current"]
    app.dependency_overrides[get_copilot_conversation_service] = lambda: svc

    client = TestClient(app)

    # User A creates & chats in WS A
    r_a = client.post(
        "/api/v1/copilot/chat",
        json={"workspaceId": str(ws_a_id), "message": "WS A summary", "requestId": "iso-1"},
    )
    assert r_a.status_code == 200
    assert "hashed_password_123" not in r_a.text
    conv_a_id = r_a.json()["conversation"]["id"]

    # Switch to User B: cannot access WS A (403) and cannot access conv_a_id via WS B (404)
    active_user["current"] = user_b
    assert client.get(f"/api/v1/copilot/conversations?workspaceId={ws_a_id}").status_code == 403
    assert client.get(f"/api/v1/copilot/conversations/{conv_a_id}?workspaceId={ws_a_id}").status_code == 403
    assert client.get(f"/api/v1/copilot/conversations/{conv_a_id}?workspaceId={ws_b_id}").status_code == 404
    assert client.post(
        "/api/v1/copilot/chat",
        json={"workspaceId": str(ws_b_id), "conversationId": conv_a_id, "message": "Steal WS A"},
    ).status_code == 404
    assert client.delete(f"/api/v1/copilot/conversations/{conv_a_id}?workspaceId={ws_b_id}").status_code == 404
