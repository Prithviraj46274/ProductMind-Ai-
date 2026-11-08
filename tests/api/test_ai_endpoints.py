"""
ProductMind AI — AI Endpoints Integration & Diagnostic Tests
Tests GET /api/v1/ai/health and POST /api/v1/ai/test with mocked LLM service.
Guarantees credentials are never exposed and error codes are correctly mapped.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ai.exceptions import (
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
    AIServiceException,
)
from app.ai.llm_service import LLMService, get_llm_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_dependency_overrides():
    """Ensure clean dependency override state before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_ai_health_endpoint_success():
    """Verify GET /api/v1/ai/health returns 200 with configuration metadata and no credentials."""
    response = client.get("/api/v1/ai/health")
    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert data["provider"] in {"google", "openrouter", "groq"}
    assert "model" in data
    assert "is_configured" in data
    assert "temperature" in data
    assert "max_output_tokens" in data
    assert "timeout_seconds" in data
    assert "max_retries" in data

    # Security check: absolutely no sensitive keys or secrets in response
    assert "api_key" not in str(data).lower()
    assert "key" not in data
    assert "google_api_key" not in data
    assert "openrouter_api_key" not in data
    assert "groq_api_key" not in data


def test_ai_health_endpoint_groq_mocked():
    """Verify GET /api/v1/ai/health accurately reports Groq provider state."""
    mock_service = AsyncMock()
    mock_service.is_configured = True
    mock_service.provider_name = "groq"
    mock_service.model_name = "qwen/qwen3.8-27b"
    mock_service.settings = MagicMock()
    mock_service.settings.AI_TEMPERATURE = 1.0
    mock_service.settings.AI_MAX_OUTPUT_TOKENS = 4096
    mock_service.settings.AI_TIMEOUT_SECONDS = 60
    mock_service.settings.AI_MAX_RETRIES = 2

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.get("/api/v1/ai/health")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "groq"
    assert data["model"] == "qwen/qwen3.8-27b"
    assert data["temperature"] == 1.0
    assert data["status"] == "ready"


def test_ai_test_endpoint_groq_success_mocked():
    """Verify POST /api/v1/ai/test executes successfully when Groq LLM is active."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "groq"
    mock_service.model_name = "qwen/qwen3.8-27b"
    mock_service.generate_text.return_value = "Hello from Qwen 3.8 27B on Groq!"

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post(
        "/api/v1/ai/test",
        json={"prompt": "Hi Qwen"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["provider"] == "groq"
    assert data["model"] == "qwen/qwen3.8-27b"
    assert data["response"] == "Hello from Qwen 3.8 27B on Groq!"


def test_ai_health_endpoint_openrouter_mocked():
    """Verify GET /api/v1/ai/health accurately reports OpenRouter provider state."""
    mock_service = AsyncMock()
    mock_service.is_configured = True
    mock_service.provider_name = "openrouter"
    mock_service.model_name = "google/gemma-4-31b-it:free"
    mock_service.settings = MagicMock()
    mock_service.settings.AI_TEMPERATURE = 0.2
    mock_service.settings.AI_MAX_OUTPUT_TOKENS = 4096
    mock_service.settings.AI_TIMEOUT_SECONDS = 60
    mock_service.settings.AI_MAX_RETRIES = 2

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.get("/api/v1/ai/health")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openrouter"
    assert data["model"] == "google/gemma-4-31b-it:free"
    assert data["status"] == "ready"


def test_ai_test_endpoint_openrouter_success_mocked():
    """Verify POST /api/v1/ai/test executes successfully when OpenRouter LLM is active."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "openrouter"
    mock_service.model_name = "google/gemma-4-31b-it:free"
    mock_service.generate_text.return_value = "Hello from Gemma 4 31B via OpenRouter!"

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post(
        "/api/v1/ai/test",
        json={"prompt": "Hi Gemma"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["provider"] == "openrouter"
    assert data["model"] == "google/gemma-4-31b-it:free"
    assert data["response"] == "Hello from Gemma 4 31B via OpenRouter!"


def test_ai_test_endpoint_success_mocked():
    """Verify POST /api/v1/ai/test executes successfully when LLM is mocked."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "google"
    mock_service.model_name = "gemini-3.8-flash"
    mock_service.generate_text.return_value = "ProductMind AI LLM Foundation is operational!"

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post(
        "/api/v1/ai/test",
        json={
            "prompt": "Test ping prompt",
            "system_instruction": "Test system instruction",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["provider"] == "google"
    assert data["model"] == "gemini-3.8-flash"
    assert data["prompt"] == "Test ping prompt"
    assert data["response"] == "ProductMind AI LLM Foundation is operational!"
    assert data["latency_ms"] is not None
    assert data["latency_ms"] >= 0


def test_ai_test_endpoint_unconfigured_returns_503():
    """Verify POST /api/v1/ai/test returns 503 when AI is unconfigured."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = False

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post("/api/v1/ai/test", json={})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"].lower()


def test_ai_test_endpoint_auth_failure_returns_401():
    """Verify provider authentication failure maps to HTTP 401."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.generate_text.side_effect = AIAuthenticationException(
        "Invalid API key", provider="google"
    )

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post("/api/v1/ai/test", json={})
    assert response.status_code == 401
    assert "authentication failed" in response.json()["detail"].lower()


def test_ai_test_endpoint_rate_limit_returns_429():
    """Verify provider quota or rate limit maps to HTTP 429."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.generate_text.side_effect = AIRateLimitException(
        "Quota exceeded", provider="google"
    )

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post("/api/v1/ai/test", json={})
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_ai_test_endpoint_timeout_returns_504():
    """Verify request timeout maps to HTTP 504."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.generate_text.side_effect = AITimeoutException(
        "Request timed out", provider="google"
    )

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post("/api/v1/ai/test", json={})
    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_ai_test_endpoint_provider_unavailable_returns_503():
    """Verify provider 503 unavailable maps to HTTP 503."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.generate_text.side_effect = AIProviderException(
        "Google Gemini model 'gemini-3.8-flash' is currently unavailable due to high demand (503 UNAFAILABLE). Spikes in demand are temporary. Please retry shortly.",
        provider="google",
    )

    app.dependency_overrides[get_llm_service] = lambda: mock_service

    response = client.post("/api/v1/ai/test", json={})
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower() or "503" in response.json()["detail"]

