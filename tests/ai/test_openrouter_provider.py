"""
ProductMind AI — OpenRouter Provider Unit Tests
Tests provider client instantiation, caching, parameter propagation,
OpenRouter base URL, and exception mapping to standard AIServiceException hierarchy.
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
from app.ai.providers.openrouter import OpenRouterProvider, OPENROUTER_BASE_URL
from app.ai.providers import get_provider


class SampleFeatureScoring(BaseModel):
    feature_name: str
    impact_score: float
    confidence: float


@pytest.fixture
def configured_openrouter_settings():
    return AISettings(
        OPENROUTER_API_KEY="sk-or-v1-mock-test-key-for-unit-tests-only",
        AI_PROVIDER="openrouter",
        AI_MODEL="google/gemma-4-31b-it:free",
        AI_TEMPERATURE=0.2,
        AI_MAX_OUTPUT_TOKENS=4096,
        AI_TIMEOUT_SECONDS=60,
        AI_MAX_RETRIES=2,
    )


def test_openrouter_provider_properties(configured_openrouter_settings):
    """Verify provider name, model identifier, and base URL properties."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)
    assert provider.provider_name == "openrouter"
    assert provider.model_name == "google/gemma-4-31b-it:free"
    assert provider.api_base_url == "https://openrouter.ai/api/v1"


def test_openrouter_provider_unconfigured_raises_on_get_client():
    """Verify get_chat_model raises AIConfigurationException if unconfigured."""
    unconfigured = AISettings(_env_file=None, AI_PROVIDER="openrouter", OPENROUTER_API_KEY=None)
    provider = OpenRouterProvider(settings=unconfigured)
    with pytest.raises(AIConfigurationException) as exc_info:
        provider.get_chat_model()
    assert exc_info.value.provider == "openrouter"


@patch("app.ai.providers.openrouter.ChatOpenAI")
def test_openrouter_client_initialization_and_caching(mock_chat_cls, configured_openrouter_settings):
    """Verify ChatOpenAI is initialized with correct base URL, headers, and is cached."""
    mock_instance = MagicMock()
    mock_chat_cls.return_value = mock_instance

    provider = OpenRouterProvider(settings=configured_openrouter_settings)
    client1 = provider.get_chat_model()
    client2 = provider.get_chat_model()

    assert client1 is client2
    assert mock_chat_cls.call_count == 1

    _, kwargs = mock_chat_cls.call_args
    assert kwargs["model"] == "google/gemma-4-31b-it:free"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["api_key"] == "sk-or-v1-mock-test-key-for-unit-tests-only"
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 4096
    assert kwargs["timeout"] == 60
    assert kwargs["max_retries"] == 2
    assert "default_headers" in kwargs
    assert kwargs["default_headers"]["HTTP-Referer"] == "https://productmind.ai"
    assert kwargs["default_headers"]["X-Title"] == "ProductMind AI"


@pytest.mark.asyncio
async def test_openrouter_ainvoke_text_success(configured_openrouter_settings):
    """Verify asynchronous text generation with mocked ChatOpenAI."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    mock_response = MagicMock()
    mock_response.content = "OpenRouter + Gemma 4 31B is operational."

    with patch.object(provider, "get_chat_model") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.ainvoke.return_value = mock_response
        mock_get_client.return_value = mock_client

        messages = [
            SystemMessage(content="You are a PM copilot."),
            HumanMessage(content="Hello Gemma!"),
        ]
        result = await provider.ainvoke_text(messages)

        assert result == "OpenRouter + Gemma 4 31B is operational."
        mock_client.ainvoke.assert_awaited_once_with(messages)


@pytest.mark.asyncio
async def test_openrouter_ainvoke_structured_success(configured_openrouter_settings):
    """Verify structured output parsing with schema enforcement."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    expected = SampleFeatureScoring(
        feature_name="AI PM Copilot",
        impact_score=9.5,
        confidence=0.98,
    )

    with patch.object(provider, "get_chat_model") as mock_get_client:
        mock_structured_chain = AsyncMock()
        mock_structured_chain.ainvoke.return_value = expected

        mock_client = MagicMock()
        mock_client.with_structured_output.return_value = mock_structured_chain
        mock_get_client.return_value = mock_client

        result = await provider.ainvoke_structured(
            schema=SampleFeatureScoring,
            messages=[HumanMessage(content="Score this feature")],
        )

        assert isinstance(result, SampleFeatureScoring)
        assert result.feature_name == "AI PM Copilot"
        assert result.impact_score == 9.5
        assert result.confidence == 0.98


def test_openrouter_error_mapping_authentication(configured_openrouter_settings):
    """Verify 401 and invalid API key map to AIAuthenticationException."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    err = Exception("Error code: 401 - {'error': {'message': 'Invalid API Key', 'code': 401}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIAuthenticationException)
    assert mapped.provider == "openrouter"


def test_openrouter_error_mapping_rate_limit(configured_openrouter_settings):
    """Verify 429 rate limit and insufficient credits map to AIRateLimitException."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    err = Exception("Error code: 429 - {'error': {'message': 'Rate limit exceeded: free tier limit', 'code': 429}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIRateLimitException)
    assert mapped.provider == "openrouter"


def test_openrouter_error_mapping_timeout(configured_openrouter_settings):
    """Verify timeout and 504 errors map to AITimeoutException."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    err = TimeoutError("Request timed out connecting to OpenRouter")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AITimeoutException)
    assert mapped.provider == "openrouter"


def test_openrouter_error_mapping_model_unavailable(configured_openrouter_settings):
    """Verify 503 unavailable errors map to AIProviderException."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    err = Exception("Error code: 503 - {'error': {'message': 'Model temporarily unavailable', 'code': 503}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIProviderException)
    assert mapped.provider == "openrouter"
    assert "unavailable" in mapped.message.lower() or "503" in mapped.message


def test_openrouter_error_mapping_model_not_found(configured_openrouter_settings):
    """Verify 404 model not found maps to AIProviderException."""
    provider = OpenRouterProvider(settings=configured_openrouter_settings)

    err = Exception("Error code: 404 - {'error': {'message': 'No such model google/unknown:free', 'code': 404}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIProviderException)
    assert mapped.provider == "openrouter"
    assert "not found" in mapped.message.lower()


def test_provider_factory_selection(configured_openrouter_settings):
    """Verify get_provider() correctly instantiates OpenRouterProvider or GeminiProvider."""
    # OpenRouter
    openrouter_provider = get_provider(configured_openrouter_settings)
    assert isinstance(openrouter_provider, OpenRouterProvider)
    assert openrouter_provider.provider_name == "openrouter"

    # Gemini
    gemini_settings = AISettings(
        GOOGLE_API_KEY="AIzaSyMockKeyForGeminiTest",
        AI_PROVIDER="google",
        AI_MODEL="gemini-3.8-flash",
    )
    gemini_provider = get_provider(gemini_settings)
    assert gemini_provider.provider_name == "google"
