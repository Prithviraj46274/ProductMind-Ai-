"""
ProductMind AI — Groq Provider Unit Tests
Tests provider client instantiation, caching, parameter propagation,
Groq base URL, Qwen reasoning controls, and exception mapping to standard AIServiceException hierarchy.
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
from app.ai.providers.groq import GroqProvider, GROQ_BASE_URL
from app.ai.providers import get_provider


class SampleFeatureScoring(BaseModel):
    feature_name: str
    impact_score: float
    confidence: float


@pytest.fixture
def configured_groq_settings():
    return AISettings(
        _env_file=None,
        GROQ_API_KEY="gsk_mock_test_key_for_unit_tests_only",
        AI_PROVIDER="groq",
        AI_MODEL="qwen/qwen3.8-27b",
        AI_TEMPERATURE=1.0,
        AI_MAX_OUTPUT_TOKENS=4096,
        AI_TIMEOUT_SECONDS=60,
        AI_MAX_RETRIES=2,
    )


def test_groq_provider_properties(configured_groq_settings):
    """Verify provider name, model identifier, and base URL properties."""
    provider = GroqProvider(settings=configured_groq_settings)
    assert provider.provider_name == "groq"
    assert provider.model_name == "qwen/qwen3.8-27b"
    assert provider.api_base_url == "https://api.groq.com/openai/v1"


def test_groq_provider_unconfigured_raises_on_get_client():
    """Verify get_chat_model raises AIConfigurationException if unconfigured."""
    unconfigured = AISettings(_env_file=None, AI_PROVIDER="groq", GROQ_API_KEY=None)
    provider = GroqProvider(settings=unconfigured)
    with pytest.raises(AIConfigurationException) as exc_info:
        provider.get_chat_model()
    assert exc_info.value.provider == "groq"


@patch("app.ai.providers.groq.ChatGroq")
def test_groq_client_initialization_and_caching(mock_chat_cls, configured_groq_settings):
    """Verify ChatGroq is initialized with correct base URL, model, reasoning format, and is cached."""
    mock_instance = MagicMock()
    mock_chat_cls.return_value = mock_instance

    provider = GroqProvider(settings=configured_groq_settings)
    client1 = provider.get_chat_model()
    client2 = provider.get_chat_model()

    assert client1 is client2
    assert mock_chat_cls.call_count == 1

    _, kwargs = mock_chat_cls.call_args
    assert kwargs["model"] == "qwen/qwen3.8-27b"
    assert kwargs["groq_api_key"] == "gsk_mock_test_key_for_unit_tests_only"
    assert kwargs["temperature"] == 1.0
    assert kwargs["max_tokens"] == 4096
    assert kwargs["request_timeout"] == 60
    assert kwargs["max_retries"] == 2
    assert kwargs["reasoning_format"] == "hidden"


@pytest.mark.asyncio
async def test_groq_ainvoke_text_success_and_strips_thinking_tags(configured_groq_settings):
    """Verify asynchronous text generation with mocked ChatGroq and cleans <think> tags."""
    provider = GroqProvider(settings=configured_groq_settings)

    mock_response = MagicMock()
    mock_response.content = "<think>Internal deliberation about product priority</think>Groq Qwen 3.8 27B is operational."

    with patch.object(provider, "get_chat_model") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.ainvoke.return_value = mock_response
        mock_get_client.return_value = mock_client

        messages = [
            SystemMessage(content="You are a PM copilot."),
            HumanMessage(content="Hello Qwen!"),
        ]
        result = await provider.ainvoke_text(messages)

        # Confirm <think> traces were stripped from output
        assert result == "Groq Qwen 3.8 27B is operational."
        assert "<think>" not in result
        mock_client.ainvoke.assert_awaited_once_with(messages)


@pytest.mark.asyncio
async def test_groq_ainvoke_structured_success(configured_groq_settings):
    """Verify structured output parsing with schema enforcement."""
    provider = GroqProvider(settings=configured_groq_settings)

    expected = SampleFeatureScoring(
        feature_name="Fast AI Generation",
        impact_score=9.8,
        confidence=0.99,
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
        assert result.feature_name == "Fast AI Generation"
        assert result.impact_score == 9.8
        assert result.confidence == 0.99


def test_groq_error_mapping_authentication(configured_groq_settings):
    """Verify 401 and invalid API key map to AIAuthenticationException."""
    provider = GroqProvider(settings=configured_groq_settings)

    err = Exception("Error code: 401 - {'error': {'message': 'Invalid API Key', 'code': 401}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIAuthenticationException)
    assert mapped.provider == "groq"


def test_groq_error_mapping_rate_limit(configured_groq_settings):
    """Verify 429 rate limit and TPM/RPM limits map to AIRateLimitException."""
    provider = GroqProvider(settings=configured_groq_settings)

    err = Exception("Error code: 429 - {'error': {'message': 'Rate limit reached for model qwen/qwen3.8-27b in organization org_xyz on tokens per minute (TPM)', 'code': 429}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIRateLimitException)
    assert mapped.provider == "groq"


def test_groq_error_mapping_timeout(configured_groq_settings):
    """Verify timeout and 504 errors map to AITimeoutException."""
    provider = GroqProvider(settings=configured_groq_settings)

    err = TimeoutError("Request timed out connecting to Groq")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AITimeoutException)
    assert mapped.provider == "groq"


def test_groq_error_mapping_model_unavailable(configured_groq_settings):
    """Verify 503 unavailable errors map to AIProviderException."""
    provider = GroqProvider(settings=configured_groq_settings)

    err = Exception("Error code: 503 - {'error': {'message': 'Service Unavailable: model overloaded', 'code': 503}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIProviderException)
    assert mapped.provider == "groq"
    assert "unavailable" in mapped.message.lower() or "503" in mapped.message


def test_groq_error_mapping_model_not_found(configured_groq_settings):
    """Verify 404 model not found maps to AIProviderException."""
    provider = GroqProvider(settings=configured_groq_settings)

    err = Exception("Error code: 404 - {'error': {'message': 'Model qwen/unknown does not exist', 'code': 404}}")
    mapped = provider._map_exception(err)
    assert isinstance(mapped, AIProviderException)
    assert mapped.provider == "groq"
    assert "not found" in mapped.message.lower() or "does not exist" in str(mapped).lower()


def test_provider_factory_selection_groq(configured_groq_settings):
    """Verify get_provider() correctly instantiates GroqProvider, OpenRouterProvider, or GeminiProvider."""
    # Groq
    groq_provider = get_provider(configured_groq_settings)
    assert isinstance(groq_provider, GroqProvider)
    assert groq_provider.provider_name == "groq"

    # OpenRouter
    openrouter_settings = AISettings(
        _env_file=None,
        OPENROUTER_API_KEY="sk-or-v1-mock",
        AI_PROVIDER="openrouter",
        AI_MODEL="google/gemma-4-31b-it:free",
    )
    openrouter_provider = get_provider(openrouter_settings)
    assert openrouter_provider.provider_name == "openrouter"

    # Gemini
    gemini_settings = AISettings(
        _env_file=None,
        GOOGLE_API_KEY="AIzaSyMockKeyForGeminiTest",
        AI_PROVIDER="google",
        AI_MODEL="gemini-3.8-flash",
    )
    gemini_provider = get_provider(gemini_settings)
    assert gemini_provider.provider_name == "google"
