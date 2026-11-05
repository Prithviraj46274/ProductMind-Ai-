"""
ProductMind AI — Google Gemini Provider Unit Tests
Tests provider client instantiation, caching, parameter propagation,
and exception mapping to the standard AIServiceException hierarchy.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from app.ai.config import AISettings
from app.ai.exceptions import (
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
    AISchemaValidationException,
)
from app.ai.providers.gemini import GeminiProvider


class SampleStructuredOutput(BaseModel):
    summary: str
    confidence_score: float


@pytest.fixture
def configured_settings():
    return AISettings(
        GOOGLE_API_KEY="AIzaSyMockedKeyForTestingPurposes123",
        AI_PROVIDER="google",
        AI_MODEL="gemini-3.8-flash",
        AI_TEMPERATURE=0.3,
        AI_MAX_OUTPUT_TOKENS=2048,
        AI_TIMEOUT_SECONDS=45,
        AI_MAX_RETRIES=1,
    )


def test_gemini_provider_properties(configured_settings):
    """Verify provider and model identification properties."""
    provider = GeminiProvider(settings=configured_settings)
    assert provider.provider_name == "google"
    assert provider.model_name == "gemini-3.8-flash"


def test_gemini_provider_unconfigured_raises_on_get_client():
    """Verify get_chat_model raises AIConfigurationException if unconfigured."""
    unconfigured = AISettings(GOOGLE_API_KEY=None)
    provider = GeminiProvider(settings=unconfigured)
    with pytest.raises(AIConfigurationException):
        provider.get_chat_model()


@patch("app.ai.providers.gemini.ChatGoogleGenerativeAI")
def test_gemini_provider_client_caching(mock_chat_cls, configured_settings):
    """Verify get_chat_model reuses client instance when using default parameters."""
    mock_instance = MagicMock()
    mock_chat_cls.return_value = mock_instance

    provider = GeminiProvider(settings=configured_settings)
    client1 = provider.get_chat_model()
    client2 = provider.get_chat_model()

    assert client1 is client2
    assert mock_chat_cls.call_count == 1


@pytest.mark.asyncio
async def test_gemini_ainvoke_text_success(configured_settings):
    """Verify successful asynchronous text generation using mocked LangChain client."""
    provider = GeminiProvider(settings=configured_settings)

    mock_response = MagicMock()
    mock_response.content = "ProductMind AI Foundation is operational."

    with patch.object(provider, "get_chat_model") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.ainvoke.return_value = mock_response
        mock_get_client.return_value = mock_client

        messages = [
            SystemMessage(content="You are an AI Copilot."),
            HumanMessage(content="Ping"),
        ]
        result = await provider.ainvoke_text(messages)

        assert result == "ProductMind AI Foundation is operational."
        mock_client.ainvoke.assert_awaited_once_with(messages)


@pytest.mark.asyncio
async def test_gemini_ainvoke_structured_success(configured_settings):
    """Verify structured output parsing with schema enforcement."""
    provider = GeminiProvider(settings=configured_settings)

    expected_output = SampleStructuredOutput(
        summary="Feature prioritizes high user impact.",
        confidence_score=0.95,
    )

    with patch.object(provider, "get_chat_model") as mock_get_client:
        mock_structured_chain = AsyncMock()
        mock_structured_chain.ainvoke.return_value = expected_output

        mock_client = MagicMock()
        mock_client.with_structured_output.return_value = mock_structured_chain
        mock_get_client.return_value = mock_client

        result = await provider.ainvoke_structured(
            schema=SampleStructuredOutput,
            messages=[HumanMessage(content="Analyze feature impact")],
        )

        assert isinstance(result, SampleStructuredOutput)
        assert result.summary == "Feature prioritizes high user impact."
        assert result.confidence_score == 0.95


def test_gemini_error_mapping_authentication(configured_settings):
    """Verify authentication failures map to AIAuthenticationException."""
    provider = GeminiProvider(settings=configured_settings)

    auth_error = Exception("API key not valid. Please pass a valid API key.")
    mapped = provider._map_exception(auth_error)
    assert isinstance(mapped, AIAuthenticationException)
    assert mapped.provider == "google"


def test_gemini_error_mapping_rate_limit(configured_settings):
    """Verify rate limits and quota errors map to AIRateLimitException."""
    provider = GeminiProvider(settings=configured_settings)

    rate_limit_error = Exception("429 ResourceExhausted: Quota exceeded for quota metric")
    mapped = provider._map_exception(rate_limit_error)
    assert isinstance(mapped, AIRateLimitException)
    assert mapped.provider == "google"


def test_gemini_error_mapping_timeout(configured_settings):
    """Verify timeouts map to AITimeoutException."""
    provider = GeminiProvider(settings=configured_settings)

    timeout_error = TimeoutError("Request timed out waiting for backend response")
    mapped = provider._map_exception(timeout_error)
    assert isinstance(mapped, AITimeoutException)
    assert mapped.provider == "google"


def test_gemini_error_mapping_model_not_found(configured_settings):
    """Verify missing or unsupported model maps to AIProviderException."""
    provider = GeminiProvider(settings=configured_settings)

    not_found_error = Exception("404 Model not found: models/gemini-unknown-model")
    mapped = provider._map_exception(not_found_error)
    assert isinstance(mapped, AIProviderException)
    assert "not found" in str(mapped).lower()

