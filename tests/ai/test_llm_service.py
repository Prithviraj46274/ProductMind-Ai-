"""
ProductMind AI — Shared LLM Service Unit Tests
Verifies high-level generate_text, generate_chat, generate_structured,
input normalization, and agent integration interface.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.ai.config import AISettings
from app.ai.exceptions import (
    AIServiceException,
    AISchemaValidationException,
)
from app.ai.llm_service import LLMService, get_llm_service
from app.ai.providers.base import BaseLLMProvider
from app.ai.schemas import ChatMessageInput


class ProductFeatureScore(BaseModel):
    feature_name: str
    impact_score: int
    rationale: str


@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=BaseLLMProvider)
    provider.provider_name = "google"
    provider.model_name = "gemini-3.8-flash"
    provider.ainvoke_text = AsyncMock()
    provider.ainvoke_structured = AsyncMock()
    return provider


@pytest.fixture
def configured_settings():
    return AISettings(GOOGLE_API_KEY="AIzaSyMockedKey123")


@pytest.mark.asyncio
async def test_llm_service_generate_text(mock_provider, configured_settings):
    """Verify generate_text builds correct LangChain message sequence."""
    service = LLMService(provider=mock_provider, settings=configured_settings)
    mock_provider.ainvoke_text.return_value = "Prioritization complete."

    result = await service.generate_text(
        prompt="Rank top features",
        system_instruction="You are a PM prioritization agent.",
    )

    assert result == "Prioritization complete."
    mock_provider.ainvoke_text.assert_awaited_once()
    called_messages = mock_provider.ainvoke_text.await_args[0][0]
    assert len(called_messages) == 2
    assert isinstance(called_messages[0], SystemMessage)
    assert called_messages[0].content == "You are a PM prioritization agent."
    assert isinstance(called_messages[1], HumanMessage)
    assert called_messages[1].content == "Rank top features"


@pytest.mark.asyncio
async def test_llm_service_generate_text_rejects_empty_prompt(mock_provider, configured_settings):
    """Verify generate_text rejects empty or whitespace prompt."""
    service = LLMService(provider=mock_provider, settings=configured_settings)

    with pytest.raises(AIServiceException) as exc_info:
        await service.generate_text(prompt="   ")
    assert "Prompt cannot be empty" in str(exc_info.value)


@pytest.mark.asyncio
async def test_llm_service_generate_chat(mock_provider, configured_settings):
    """Verify generate_chat normalizes mixed message representations."""
    service = LLMService(provider=mock_provider, settings=configured_settings)
    mock_provider.ainvoke_text.return_value = "Feedback summarized."

    messages = [
        {"role": "system", "content": "You are ProductMind AI Feedback Analyzer."},
        ChatMessageInput(role="user", content="Here are 10 user tickets."),
        AIMessage(content="Understood. What aspects would you like highlighted?"),
        HumanMessage(content="Focus on onboarding friction."),
    ]

    result = await service.generate_chat(messages)

    assert result == "Feedback summarized."
    called_messages = mock_provider.ainvoke_text.await_args[0][0]
    assert len(called_messages) == 4
    assert isinstance(called_messages[0], SystemMessage)
    assert isinstance(called_messages[1], HumanMessage)
    assert isinstance(called_messages[2], AIMessage)
    assert isinstance(called_messages[3], HumanMessage)


@pytest.mark.asyncio
async def test_llm_service_generate_structured(mock_provider, configured_settings):
    """Verify generate_structured delegates to provider with schema."""
    service = LLMService(provider=mock_provider, settings=configured_settings)

    expected = ProductFeatureScore(
        feature_name="One-Click SSO",
        impact_score=9,
        rationale="Unblocks enterprise tier onboarding.",
    )
    mock_provider.ainvoke_structured.return_value = expected

    result = await service.generate_structured(
        schema=ProductFeatureScore,
        prompt="Score One-Click SSO",
        system_instruction="Output structured scoring.",
    )

    assert result == expected
    assert result.impact_score == 9
    mock_provider.ainvoke_structured.assert_awaited_once()


def test_get_llm_service_singleton_behavior():
    """Verify get_llm_service returns a persistent singleton when unparametrized."""
    service1 = get_llm_service()
    service2 = get_llm_service()
    assert service1 is service2

