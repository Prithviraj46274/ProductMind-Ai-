"""
ProductMind AI — LLM Providers Registry & Factory
"""

from typing import Optional
from app.ai.config import AISettings, ai_settings
from app.ai.providers.base import BaseLLMProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.exceptions import AIConfigurationException

__all__ = [
    "BaseLLMProvider",
    "GeminiProvider",
    "get_provider",
]


def get_provider(settings: Optional[AISettings] = None) -> BaseLLMProvider:
    """
    Factory function returning the active LLM provider instance based on settings.
    Allows seamlessly introducing additional providers in the future.
    """
    active_settings = settings or ai_settings
    provider_name = active_settings.AI_PROVIDER.lower()

    if provider_name == "google":
        return GeminiProvider(settings=active_settings)

    raise AIConfigurationException(
        f"Unsupported or unrecognized AI_PROVIDER: '{provider_name}'",
        provider=provider_name,
    )

