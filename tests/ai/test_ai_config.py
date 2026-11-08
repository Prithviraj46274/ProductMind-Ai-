"""
ProductMind AI — AI Configuration Unit Tests
Verifies environment-based settings, defaults, validation rules,
credential masking, and safe error handling.
"""

import pytest
from pydantic import ValidationError

from app.ai.config import AISettings
from app.ai.exceptions import AIConfigurationException


def test_ai_settings_default_values():
    """Verify default parameters match architectural specification."""
    settings = AISettings(
        _env_file=None,
        GOOGLE_API_KEY="test_key_123",
        AI_PROVIDER="google",
        AI_MODEL="gemini-3.8-flash",
        AI_TEMPERATURE=0.2,
    )
    assert settings.AI_PROVIDER == "google"
    assert settings.AI_MODEL == "gemini-3.8-flash"
    assert settings.AI_TEMPERATURE == 0.2
    assert settings.AI_MAX_OUTPUT_TOKENS == 4096
    assert settings.AI_TIMEOUT_SECONDS == 60
    assert settings.AI_MAX_RETRIES == 2
    assert settings.is_configured is True


def test_ai_settings_is_configured_logic():
    """Verify is_configured correctly checks for real keys vs missing/placeholder keys."""
    # Real key
    s_real = AISettings(_env_file=None, AI_PROVIDER="google", GOOGLE_API_KEY="AIzaSyRealKeySecretValue")
    assert s_real.is_configured is True

    # None
    s_none = AISettings(_env_file=None, AI_PROVIDER="google", GOOGLE_API_KEY=None)
    assert s_none.is_configured is False

    # Empty string / whitespace
    s_empty = AISettings(_env_file=None, AI_PROVIDER="google", GOOGLE_API_KEY="   ")
    assert s_empty.is_configured is False

    # Placeholder patterns
    s_placeholder = AISettings(_env_file=None, AI_PROVIDER="google", GOOGLE_API_KEY="your_google_api_key")
    assert s_placeholder.is_configured is False


def test_ai_settings_safe_dict_never_exposes_key():
    """Verify safe_dict() omits GOOGLE_API_KEY completely."""
    secret_key = "AIzaSySuperSecretKeyDoNotExpose12345"
    settings = AISettings(
        _env_file=None,
        AI_PROVIDER="google",
        AI_MODEL="gemini-3.8-flash",
        GOOGLE_API_KEY=secret_key,
    )
    safe = settings.safe_dict()

    assert "GOOGLE_API_KEY" not in safe
    assert "api_key" not in safe
    assert secret_key not in str(safe)
    assert safe["provider"] == "google"
    assert safe["model"] == "gemini-3.8-flash"
    assert safe["is_configured"] is True


def test_ai_settings_validate_for_execution_raises_when_unconfigured():
    """Verify validate_for_execution() raises safe AIConfigurationException when unconfigured."""
    settings = AISettings(_env_file=None, AI_PROVIDER="google", GOOGLE_API_KEY=None)
    with pytest.raises(AIConfigurationException) as exc_info:
        settings.validate_for_execution()

    assert "Google Gemini API key is not configured" in str(exc_info.value)
    assert exc_info.value.provider == "google"


def test_ai_settings_openrouter_configuration():
    """Verify OpenRouter provider configuration and defaults."""
    settings = AISettings(
        OPENROUTER_API_KEY="sk-or-v1-testkey123456",
        AI_PROVIDER="openrouter",
        AI_MODEL="google/gemma-4-31b-it:free",
    )
    assert settings.AI_PROVIDER == "openrouter"
    assert settings.AI_MODEL == "google/gemma-4-31b-it:free"
    assert settings.is_configured is True


def test_ai_settings_openrouter_is_configured_logic():
    """Verify is_configured for OpenRouter provider with valid and invalid keys."""
    # Valid key
    s_valid = AISettings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="sk-or-v1-real-key-value",
    )
    assert s_valid.is_configured is True

    # None
    s_none = AISettings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=None,
    )
    assert s_none.is_configured is False

    # Empty / whitespace
    s_empty = AISettings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="   ",
    )
    assert s_empty.is_configured is False

    # Placeholder pattern
    s_placeholder = AISettings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="your_openrouter_api_key",
    )
    assert s_placeholder.is_configured is False


def test_ai_settings_openrouter_validate_for_execution():
    """Verify validate_for_execution raises AIConfigurationException with openrouter message."""
    s_unconfigured = AISettings(
        AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=None,
    )
    with pytest.raises(AIConfigurationException) as exc_info:
        s_unconfigured.validate_for_execution()

    assert "OpenRouter API key is not configured" in str(exc_info.value)
    assert exc_info.value.provider == "openrouter"


def test_ai_settings_openrouter_safe_dict():
    """Verify safe_dict() omits OPENROUTER_API_KEY completely."""
    secret_key = "sk-or-v1-supersecretkeyneverexpose"
    settings = AISettings(
        _env_file=None,
        AI_PROVIDER="openrouter",
        AI_MODEL="google/gemma-4-31b-it:free",
        OPENROUTER_API_KEY=secret_key,
    )
    safe = settings.safe_dict()

    assert "OPENROUTER_API_KEY" not in safe
    assert "api_key" not in safe
    assert secret_key not in str(safe)
    assert safe["provider"] == "openrouter"
    assert safe["model"] == "google/gemma-4-31b-it:free"
    assert safe["is_configured"] is True


def test_ai_settings_groq_configuration():
    """Verify Groq provider configuration and defaults."""
    settings = AISettings(
        _env_file=None,
        GROQ_API_KEY="gsk_mock_test_key_123456",
        AI_PROVIDER="groq",
        AI_MODEL="qwen/qwen3.8-27b",
        AI_TEMPERATURE=1.0,
    )
    assert settings.AI_PROVIDER == "groq"
    assert settings.AI_MODEL == "qwen/qwen3.8-27b"
    assert settings.AI_TEMPERATURE == 1.0
    assert settings.is_configured is True


def test_ai_settings_groq_is_configured_logic():
    """Verify is_configured for Groq provider with valid and invalid keys."""
    # Valid key
    s_valid = AISettings(
        _env_file=None,
        AI_PROVIDER="groq",
        GROQ_API_KEY="gsk_real_key_value_123",
    )
    assert s_valid.is_configured is True

    # None
    s_none = AISettings(
        _env_file=None,
        AI_PROVIDER="groq",
        GROQ_API_KEY=None,
    )
    assert s_none.is_configured is False

    # Empty / whitespace
    s_empty = AISettings(
        _env_file=None,
        AI_PROVIDER="groq",
        GROQ_API_KEY="   ",
    )
    assert s_empty.is_configured is False

    # Placeholder pattern
    s_placeholder = AISettings(
        _env_file=None,
        AI_PROVIDER="groq",
        GROQ_API_KEY="your_groq_api_key",
    )
    assert s_placeholder.is_configured is False


def test_ai_settings_groq_validate_for_execution():
    """Verify validate_for_execution raises AIConfigurationException with Groq message."""
    s_unconfigured = AISettings(
        _env_file=None,
        AI_PROVIDER="groq",
        GROQ_API_KEY=None,
    )
    with pytest.raises(AIConfigurationException) as exc_info:
        s_unconfigured.validate_for_execution()

    assert "Groq API key is not configured" in str(exc_info.value)
    assert exc_info.value.provider == "groq"


def test_ai_settings_groq_safe_dict():
    """Verify safe_dict() omits GROQ_API_KEY completely."""
    secret_key = "gsk_supersecretkeyneverexposetoanyone"
    settings = AISettings(
        _env_file=None,
        AI_PROVIDER="groq",
        AI_MODEL="qwen/qwen3.8-27b",
        GROQ_API_KEY=secret_key,
    )
    safe = settings.safe_dict()

    assert "GROQ_API_KEY" not in safe
    assert "api_key" not in safe
    assert secret_key not in str(safe)
    assert safe["provider"] == "groq"
    assert safe["model"] == "qwen/qwen3.8-27b"
    assert safe["is_configured"] is True


def test_ai_settings_rejects_unsupported_provider():
    """Verify validator rejects unsupported provider names."""
    with pytest.raises(ValidationError) as exc_info:
        AISettings(AI_PROVIDER="unsupported_provider_xyz")
    assert "Unsupported AI_PROVIDER" in str(exc_info.value)


def test_ai_settings_rejects_out_of_range_temperature():
    """Verify temperature range validation (0.0 <= temp <= 2.0)."""
    with pytest.raises(ValidationError):
        AISettings(AI_TEMPERATURE=2.5)

    with pytest.raises(ValidationError):
        AISettings(AI_TEMPERATURE=-0.1)


def test_ai_settings_rejects_non_positive_tokens():
    """Verify max_output_tokens must be > 0."""
    with pytest.raises(ValidationError):
        AISettings(AI_MAX_OUTPUT_TOKENS=0)

