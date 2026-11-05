"""
ProductMind AI — Shared LLM Service
Provides high-level, unified AI generation capabilities for all downstream
ProductMind AI agents (Feedback Intelligence, Prioritization, PRD, and PM Copilot).
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessage,
)

from app.ai.config import AISettings, ai_settings
from app.ai.exceptions import (
    AIServiceException,
    AIConfigurationException,
)
from app.ai.providers.base import BaseLLMProvider
from app.ai.providers import get_provider
from app.ai.schemas import ChatMessageInput

logger = logging.getLogger("productmind.ai.llm_service")
T = TypeVar("T", bound=BaseModel)


class LLMService:
    """
    Central, reusable AI service for ProductMind AI.
    Exposes unified text generation, message-based chat, and schema-enforced structured output.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        settings: Optional[AISettings] = None,
    ):
        self.settings: AISettings = settings or ai_settings
        self.provider: BaseLLMProvider = provider or get_provider(self.settings)

    @property
    def is_configured(self) -> bool:
        """Indicates if active provider has valid credentials."""
        return self.settings.is_configured

    @property
    def provider_name(self) -> str:
        """Name of active LLM provider."""
        return self.provider.provider_name

    @property
    def model_name(self) -> str:
        """Configured model identifier."""
        return self.provider.model_name

    def get_chat_model(self, **kwargs: Any) -> BaseChatModel:
        """
        Direct access to underlying LangChain BaseChatModel for custom chains or agent executors.
        """
        return self.provider.get_chat_model(**kwargs)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generates standard text from a user prompt and optional system instruction.
        """
        if not prompt or not prompt.strip():
            raise AIServiceException("Prompt cannot be empty.", provider=self.provider_name)

        messages: List[BaseMessage] = []
        if system_instruction and system_instruction.strip():
            messages.append(SystemMessage(content=system_instruction.strip()))
        messages.append(HumanMessage(content=prompt.strip()))

        return await self.provider.ainvoke_text(messages, **kwargs)

    async def generate_chat(
        self,
        messages: List[Union[BaseMessage, ChatMessageInput, Dict[str, str]]],
        **kwargs: Any,
    ) -> str:
        """
        Generates a text completion from a sequence of chat messages.
        Accepts LangChain BaseMessage instances, ChatMessageInput schemas, or raw dicts.
        """
        if not messages:
            raise AIServiceException("Message list cannot be empty.", provider=self.provider_name)

        normalized_messages: List[BaseMessage] = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                normalized_messages.append(msg)
            elif isinstance(msg, ChatMessageInput):
                if msg.role == "system":
                    normalized_messages.append(SystemMessage(content=msg.content))
                elif msg.role == "assistant":
                    normalized_messages.append(AIMessage(content=msg.content))
                else:
                    normalized_messages.append(HumanMessage(content=msg.content))
            elif isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    normalized_messages.append(SystemMessage(content=content))
                elif role in ("assistant", "ai"):
                    normalized_messages.append(AIMessage(content=content))
                else:
                    normalized_messages.append(HumanMessage(content=content))
            else:
                raise AIServiceException(
                    f"Unsupported message type: {type(msg).__name__}",
                    provider=self.provider_name,
                )

        return await self.provider.ainvoke_text(normalized_messages, **kwargs)

    async def generate_structured(
        self,
        schema: Type[T],
        prompt: str,
        system_instruction: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        """
        Generates structured JSON output validated against a Pydantic model schema.
        Used by ProductMind AI intelligence agents to produce strongly-typed insights,
        scoring criteria, and PRD sections.
        """
        if not prompt or not prompt.strip():
            raise AIServiceException("Prompt cannot be empty.", provider=self.provider_name)

        messages: List[BaseMessage] = []
        if system_instruction and system_instruction.strip():
            messages.append(SystemMessage(content=system_instruction.strip()))
        messages.append(HumanMessage(content=prompt.strip()))

        return await self.provider.ainvoke_structured(schema, messages, **kwargs)


# Singleton LLM service cache
_global_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    FastAPI dependency returning the active LLMService singleton instance.
    """
    global _global_llm_service
    if _global_llm_service is None:
        _global_llm_service = LLMService()
    return _global_llm_service


def create_llm_service(
    provider: Optional[BaseLLMProvider] = None,
    settings: Optional[AISettings] = None,
) -> LLMService:
    """
    Factory function creating an LLMService instance with explicit provider or settings.
    Useful for testing or specialized model configurations.
    """
    return LLMService(provider=provider, settings=settings)


