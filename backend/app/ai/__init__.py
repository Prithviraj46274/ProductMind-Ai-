"""
ProductMind AI — AI Foundation Package
Exposes shared LLM service, provider registry, configuration, and exception classes.
"""

from app.ai.config import AISettings, ai_settings
from app.ai.exceptions import (
    AIServiceException,
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
    AISchemaValidationException,
)
from app.ai.providers.base import BaseLLMProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.groq import GroqProvider
from app.ai.llm_service import LLMService, get_llm_service, create_llm_service
from app.ai.schemas import (
    ChatMessageInput,
    AIHealthResponse,
    AITestRequest,
    AITestResponse,
)

__all__ = [
    "ai_settings",
    "AISettings",
    "BaseLLMProvider",
    "GeminiProvider",
    "OpenRouterProvider",
    "GroqProvider",
    "LLMService",
    "get_llm_service",
    "create_llm_service",
    "AIServiceException",
    "AIConfigurationException",
    "AIAuthenticationException",
    "AIRateLimitException",
    "AITimeoutException",
    "AIProviderException",
    "AISchemaValidationException",
    "ChatMessageInput",
    "AIHealthResponse",
    "AITestRequest",
    "AITestResponse",
]

