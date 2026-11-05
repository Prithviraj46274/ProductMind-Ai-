"""
ProductMind AI — Google Gemini LLM Provider
Implements LangChain ChatGoogleGenerativeAI integration with connection reuse,
retry configuration, and comprehensive domain error mapping.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

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

logger = logging.getLogger("productmind.ai.gemini")
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(BaseLLMProvider):
    """
    Production-grade LangChain integration for Google Gemini models.
    Manages client lifecycle, temperature/token limits, and robust exception mapping.
    """

    def __init__(self, settings: Optional[AISettings] = None):
        self.settings: AISettings = settings or ai_settings
        self._cached_client: Optional[ChatGoogleGenerativeAI] = None

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def model_name(self) -> str:
        return self.settings.AI_MODEL

    def get_chat_model(
        self,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatGoogleGenerativeAI:
        """
        Retrieves an initialized ChatGoogleGenerativeAI instance.
        Reuses cached instance if using default parameters.
        """
        # Validate that credentials are present before attempting initialization
        self.settings.validate_for_execution()

        # Check if custom parameters were provided
        has_custom_params = any(
            p is not None for p in [temperature, max_output_tokens, timeout, max_retries]
        ) or bool(kwargs)

        if not has_custom_params and self._cached_client is not None:
            return self._cached_client

        # Gemini 3 series compatibility:
        # Per Google developer guidelines, Gemini 3 reasoning models recommend temperature=1.0
        # (or model default). Legacy low temperatures like 0.2 degrade reasoning performance.
        is_gemini_3 = self.settings.AI_MODEL.lower().startswith("gemini-3")
        if temperature is not None:
            resolved_temperature = temperature
        elif is_gemini_3 and self.settings.AI_TEMPERATURE == 0.2:
            resolved_temperature = 1.0
        else:
            resolved_temperature = self.settings.AI_TEMPERATURE

        # Filter out legacy thinking_budget if present when calling Gemini 3 models
        filtered_kwargs = dict(kwargs)
        if is_gemini_3 and "thinking_budget" in filtered_kwargs:
            filtered_kwargs.pop("thinking_budget")

        try:
            client = ChatGoogleGenerativeAI(
                model=self.settings.AI_MODEL,
                google_api_key=self.settings.GOOGLE_API_KEY,
                temperature=resolved_temperature,
                max_output_tokens=max_output_tokens if max_output_tokens is not None else self.settings.AI_MAX_OUTPUT_TOKENS,
                timeout=timeout if timeout is not None else self.settings.AI_TIMEOUT_SECONDS,
                max_retries=max_retries if max_retries is not None else self.settings.AI_MAX_RETRIES,
                **filtered_kwargs,
            )

            if not has_custom_params:
                self._cached_client = client

            return client
        except Exception as exc:
            raise self._map_exception(exc)

    async def ainvoke_text(
        self,
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> str:
        """Invokes Gemini and returns generated text response."""
        client = self.get_chat_model(**kwargs)
        try:
            response = await client.ainvoke(messages)
            content = response.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Handle multimodal or chunked parts
                return "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content)
        except Exception as exc:
            raise self._map_exception(exc)

    async def ainvoke_structured(
        self,
        schema: Type[T],
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> T:
        """Invokes Gemini with structured output enforced to target Pydantic schema."""
        client = self.get_chat_model(**kwargs)
        try:
            structured_chain = client.with_structured_output(schema)
            raw_result = await structured_chain.ainvoke(messages)

            if isinstance(raw_result, schema):
                return raw_result
            elif isinstance(raw_result, dict):
                return schema(**raw_result)
            else:
                raise AISchemaValidationException(
                    f"Output cannot be converted to {schema.__name__}: {raw_result}",
                    provider=self.provider_name,
                )
        except (ValidationError, TypeError) as val_err:
            raise AISchemaValidationException(
                f"Model response failed validation for {schema.__name__}: {val_err}",
                provider=self.provider_name,
                original_exception=val_err,
            )
        except Exception as exc:
            raise self._map_exception(exc)

    def _map_exception(self, exc: Exception) -> AIServiceException:
        """
        Translates provider and Google API errors into standardized AIServiceException types.
        Prevents leaking API keys or internal stack traces.
        """
        if isinstance(exc, AIServiceException):
            return exc

        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        # 1. Authentication / Permission errors (401, 403, invalid API key)
        if (
            "unauthenticated" in exc_type
            or "permissiondenied" in exc_type
            or "api_key_invalid" in exc_str
            or "api key not valid" in exc_str
            or "invalid api key" in exc_str
            or "permission denied" in exc_str
            or "401" in exc_str
            or "403" in exc_str
        ):
            return AIAuthenticationException(
                "Google Gemini authentication failed. Verify that GOOGLE_API_KEY is valid.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 2. Rate limit / Quota exhaustion (429, ResourceExhausted)
        if (
            "resourceexhausted" in exc_type
            or "429" in exc_str
            or "quota" in exc_str
            or "rate limit" in exc_str
            or "resource exhausted" in exc_str
        ):
            return AIRateLimitException(
                "Google Gemini rate limit or quota exceeded. Please retry later.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 3. Timeout & Deadline Exceeded errors (504, DEADLINE_EXCEEDED, asyncio.TimeoutError)
        if (
            "deadlineexceeded" in exc_type
            or "timeout" in exc_type
            or isinstance(exc, (asyncio.TimeoutError, TimeoutError))
            or "timed out" in exc_str
            or "deadline exceeded" in exc_str
            or "deadline_exceeded" in exc_str
            or "504" in exc_str
        ):
            return AITimeoutException(
                f"Google Gemini request exceeded timeout threshold ({self.settings.AI_TIMEOUT_SECONDS}s).",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 4. Service Unavailable & High Demand (503, UNAVAILABLE)
        if (
            "unavailable" in exc_type
            or "503" in exc_str
            or "unavailable" in exc_str
            or "high demand" in exc_str
        ):
            return AIProviderException(
                f"Google Gemini model '{self.model_name}' is currently unavailable due to high demand (503 UNAVAILABLE). Spikes in demand are temporary. Please retry shortly.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 5. Model not found or unsupported
        if "notfound" in exc_type or "404" in exc_str or "not found" in exc_str:
            return AIProviderException(
                f"Configured Google Gemini model '{self.model_name}' is not found or unsupported.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 6. General provider error
        return AIProviderException(
            f"Google Gemini service error: {type(exc).__name__}",
            provider=self.provider_name,
            original_exception=exc,
        )

