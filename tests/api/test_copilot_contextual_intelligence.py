"""Phase 4.6 tests for Contextual Intelligence: intent detection, follow-up resolution, cross-domain synthesis, and missing-data diagnostics."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from langchain_core.messages import AIMessage, HumanMessage
import pytest

from app.core.enums import PlatformRole
from app.models.auth import User, Workspace
from app.models.feedback import FeedbackItem
from app.models.intelligence import FeatureGroup
from app.models.planning import PrioritizationScenario
from app.services.copilot_ai_service import (
    CopilotAIService,
    classify_question_intent,
)
from app.services.copilot_context_service import CopilotContextService


def _make_user() -> User:
    return User(
        _id=ObjectId(),
        name="PM Tester",
        email="pm@example.com",
        passwordHash="hashed_password_123",
        platformRole=PlatformRole.USER,
        isActive=True,
    )


def _make_ctx_service(ws_id: ObjectId, owner_id: ObjectId, with_analytics: bool = False):
    ws = Workspace(_id=ws_id, name="Apex WS", slug="apex-ws", ownerId=owner_id)
    ws_repo = MagicMock(find_by_id=AsyncMock(return_value=ws))
    mem_repo = MagicMock(find_membership=AsyncMock(return_value=None))

    fg_id = ObjectId()
    fb_items = [
        FeedbackItem(
            _id=ObjectId(),
            workspaceId=ws_id,
            title="Onboarding setup is confusing",
            description="Users get stuck on workspace onboarding step 2.",
            createdAt=datetime.now(timezone.utc),
        ),
        FeedbackItem(
            _id=ObjectId(),
            workspaceId=ws_id,
            title="CSV export timeout",
            description="Bulk export fails above 10k rows.",
            createdAt=datetime.now(timezone.utc),
        ),
    ]
    fb_repo = MagicMock(
        summarize_workspace_feedback=AsyncMock(
            return_value={
                "totalCount": 2,
                "sentimentDistribution": {"negative": 2},
                "priorityDistribution": {"high": 2},
                "topCategories": [{"category": "ux", "count": 1}],
                "topThemes": ["onboarding", "export"],
            }
        ),
        find_page=AsyncMock(return_value=(fb_items, 2)),
    )
    fg_repo = MagicMock(
        count=AsyncMock(return_value=1),
        find_by_workspace_and_filters=AsyncMock(
            return_value=[
                FeatureGroup(
                    _id=fg_id,
                    workspaceId=ws_id,
                    title="Guided Onboarding Flow",
                    feedbackCount=5,
                    painPoints=["Users drop at step 2"],
                    commonThemes=["onboarding"],
                )
            ]
        ),
    )
    p_repo = MagicMock(
        count=AsyncMock(return_value=1),
        find_ranked_by_score=AsyncMock(
            return_value=[
                PrioritizationScenario(
                    _id=ObjectId(),
                    workspaceId=ws_id,
                    name="Guided Onboarding Flow",
                    featureGroupId=fg_id,
                    finalScore=84.0,
                    priorityLevel="high",
                    factorScores={"feedback_frequency": 8.5, "usage_impact": 7.0},
                    factorWeights={"feedback_frequency": 0.25, "usage_impact": 0.15},
                    aiMetadata={"usage_analytics_evidence": {"adoptionPercent": 22.0}} if with_analytics else {},
                )
            ]
        ),
    )
    ae_repo = MagicMock(
        aggregate_range_overview=AsyncMock(
            return_value={"totalEvents": 500 if with_analytics else 0, "uniqueActors": 40, "uniqueSessions": 80, "avgDurationSeconds": 10.0}
        ),
        aggregate_feature_page=AsyncMock(return_value={"items": []}),
    )
    ar_repo = MagicMock(find_ingested_range=AsyncMock(return_value=[]))
    prd_repo = MagicMock(
        count=AsyncMock(return_value=0),
        find_by_workspace_and_filters=AsyncMock(return_value=[]),
    )
    rm_repo = MagicMock(count=AsyncMock(return_value=0), find_by_workspace=AsyncMock(return_value=[]))

    return CopilotContextService(
        workspace_repo=ws_repo,
        membership_repo=mem_repo,
        feedback_repo=fb_repo,
        feature_group_repo=fg_repo,
        prioritization_repo=p_repo,
        analytics_event_repo=ae_repo,
        analytics_rollup_repo=ar_repo,
        prd_repo=prd_repo,
        roadmap_repo=rm_repo,
    )


def test_intent_classification_and_followup_resolution():
    intent_fb, domains_fb, _ = classify_question_intent("What are customers complaining about most?")
    assert intent_fb == "feedback_intelligence"
    assert domains_fb[0] == "feedback"

    intent_pr, domains_pr, _ = classify_question_intent("Why did this receive a priority score of 85?")
    assert intent_pr == "prioritization_intelligence"
    assert domains_pr[0] == "prioritization"

    intent_an, domains_an, _ = classify_question_intent("What is the user drop-off rate and adoption?")
    assert intent_an == "product_analytics"
    assert domains_an[0] == "analytics"

    intent_pl, domains_pl, _ = classify_question_intent("What PRDs and roadmap items are planned?")
    assert intent_pl == "product_planning"
    assert domains_pl[0] == "planning"

    intent_cd, _, _ = classify_question_intent("Which requested features have high customer demand and low adoption?")
    assert intent_cd == "cross_domain"

    # Follow-up "Why?" inherits prior analytics turn without extra LLM call
    hist = [
        HumanMessage(content="What is the usage and adoption rate?"),
        AIMessage(content="Export has the highest adoption at 65%."),
    ]
    intent_fu, domains_fu, is_fu = classify_question_intent("Why?", history_messages=hist)
    assert is_fu is True
    assert intent_fu == "product_analytics"
    assert domains_fu[0] == "analytics"


@pytest.mark.asyncio
async def test_cross_domain_topic_reordering_and_missing_data_diagnostics():
    user = _make_user()
    ws_id = ObjectId()
    ctx_svc = _make_ctx_service(ws_id, user.id, with_analytics=False)

    ctx = await ctx_svc.get_workspace_context(
        str(ws_id),
        user,
        question="Customers are complaining about onboarding. Is this reflected in our analytics?",
    )

    # Topic-matched item ("Onboarding setup is confusing") is prioritized first
    assert "Onboarding" in ctx.feedback.items[0].title
    # Missing analytics & small feedback sample are explicitly flagged
    assert any("analytics data is unavailable" in d.lower() for d in ctx.metadata.data_limitations)
    assert any("sample is small" in d.lower() for d in ctx.metadata.data_limitations)
    # Cross-domain link explicitly marks analytics as unverified instead of fabricating
    assert any(
        link.get("type") == "unverified_analytics_mapping" and link.get("analyticsVerified") is False
        for link in ctx.metadata.cross_domain_links
    )
    assert any(
        link.get("type") == "prioritization_link" and link.get("featureGroupTitle") == "Guided Onboarding Flow"
        for link in ctx.metadata.cross_domain_links
    )


@pytest.mark.asyncio
async def test_copilot_ai_service_passes_cross_domain_diagnostics_and_followup():
    user = _make_user()
    ws_id = ObjectId()
    ctx_svc = _make_ctx_service(ws_id, user.id, with_analytics=False)

    llm = MagicMock()
    llm.provider_name = "groq"
    llm.model_name = "qwen/qwen3.8-27b"
    llm.provider = MagicMock(metrics=None)
    llm.generate_chat = AsyncMock(return_value="Direct Answer: Analytics data is unavailable.")

    ai_svc = CopilotAIService(context_service=ctx_svc, llm_service=llm)
    res = await ai_svc.ask(
        workspace_id=str(ws_id),
        user=user,
        question="Why?",
        conversation_history=[
            {"role": "user", "content": "What is our feature usage and adoption?"},
            {"role": "assistant", "content": "Analytics data is currently unavailable."},
        ],
    )

    assert llm.generate_chat.await_count == 1
    assert res.context_metadata["isFollowUp"] is True
    assert res.context_metadata["intentCategory"] == "product_analytics"
    assert res.context_metadata["dataLimitations"]
    sent_user_msg = llm.generate_chat.await_args.args[0][-1].content
    assert "crossDomainLinks" in sent_user_msg
    assert "dataLimitations" in sent_user_msg

