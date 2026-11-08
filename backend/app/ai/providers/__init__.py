"""
ProductMind AI — LLM Providers Registry & Factory
"""

from typing import Optional
from app.ai.config import AISettings, ai_settings
from app.ai.providers.base import BaseLLMProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openrouter import OpenRouterProvider
from app.ai.providers.groq import GroqProvider
from app.ai.exceptions import AIConfigurationException

__all__ = [
    "BaseLLMProvider",
    "GeminiProvider",
    "OpenRouterProvider",
    "GroqProvider",
    "get_provider",
]


def get_provider(settings: Optional[AISettings] = None) -> BaseLLMProvider:
    """
    Factory function returning the active LLM provider instance based on settings.
    Supports 'google' (Gemini), 'openrouter' (Gemma/OpenRouter), and 'groq' (Qwen/Groq).
    """
    active_settings = settings or ai_settings
    provider_name = active_settings.AI_PROVIDER.lower()

    if provider_name == "google":
        return GeminiProvider(settings=active_settings)
    elif provider_name == "openrouter":
        return OpenRouterProvider(settings=active_settings)
    elif provider_name == "groq":
        return GroqProvider(settings=active_settings)

    raise AIConfigurationException(
        f"Unsupported or unrecognized AI_PROVIDER: '{provider_name}'",
        provider=provider_name,
    )

