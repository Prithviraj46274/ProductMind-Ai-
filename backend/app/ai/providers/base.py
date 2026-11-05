"""
ProductMind AI — Base LLM Provider Abstraction
Establishes provider-agnostic interface allowing future expansion to other LLM
providers (Anthropic, OpenAI, etc.) without modifying downstream agent logic.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, TypeVar
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """
    Abstract contract for all ProductMind AI LLM providers.
    Enforces unified text generation, message invocation, structured output,
    and client lifecycle methods.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the canonical name of this provider (e.g., 'google')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Returns the active model identifier."""
        pass

    @abstractmethod
    def get_chat_model(self, **kwargs) -> BaseChatModel:
        """
        Returns an initialized LangChain BaseChatModel instance.
        Must reuse existing clients when configuration parameters match.
        """
        pass

    @abstractmethod
    async def ainvoke_text(
        self,
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> str:
        """
        Asynchronously sends formatted messages to the LLM and returns the text response.
        Handles provider-specific errors and wraps them in standard AIServiceException hierarchy.
        """
        pass

    @abstractmethod
    async def ainvoke_structured(
        self,
        schema: Type[T],
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> T:
        """
        Asynchronously invokes LLM with schema-enforced structured JSON output.
        Validates output against the supplied Pydantic schema class.
        """
        pass

