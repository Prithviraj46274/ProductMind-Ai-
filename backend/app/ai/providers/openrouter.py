"""
ProductMind AI — OpenRouter LLM Provider
Implements LangChain ChatOpenAI integration targeting OpenRouter's API endpoint,
specifically optimized for google/gemma-4-31b-it:free with connection reuse,
retry configuration, and comprehensive domain error mapping.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

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

logger = logging.getLogger("productmind.ai.openrouter")
T = TypeVar("T", bound=BaseModel)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(BaseLLMProvider):
    """
    Production-grade LangChain integration for OpenRouter endpoints.
    Uses ChatOpenAI with OpenRouter base URL to invoke models such as google/gemma-4-31b-it:free.
    Manages client lifecycle, temperature/token limits, and robust exception mapping.
    """

    def __init__(self, settings: Optional[AISettings] = None):
        self.settings: AISettings = settings or ai_settings
        self._cached_client: Optional[ChatOpenAI] = None

    @property
    def provider_name(self) -> str:
        return "openrouter"

    @property
    def model_name(self) -> str:
        return self.settings.AI_MODEL

    @property
    def api_base_url(self) -> str:
        return OPENROUTER_BASE_URL

    def get_chat_model(
        self,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        **kwargs: Any,
    ) -> ChatOpenAI:
        """
        Retrieves an initialized ChatOpenAI instance configured for OpenRouter.
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

        resolved_temperature = (
            temperature if temperature is not None else self.settings.AI_TEMPERATURE
        )
        resolved_max_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else self.settings.AI_MAX_OUTPUT_TOKENS
        )
        resolved_timeout = (
            timeout if timeout is not None else self.settings.AI_TIMEOUT_SECONDS
        )
        resolved_max_retries = (
            max_retries if max_retries is not None else self.settings.AI_MAX_RETRIES
        )

        try:
            client = ChatOpenAI(
                model=self.settings.AI_MODEL,
                api_key=self.settings.OPENROUTER_API_KEY,
                base_url=self.api_base_url,
                temperature=resolved_temperature,
                max_tokens=resolved_max_tokens,
                timeout=resolved_timeout,
                max_retries=resolved_max_retries,
                default_headers={
                    "HTTP-Referer": "https://productmind.ai",
                    "X-Title": "ProductMind AI",
                },
                **kwargs,
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
        """Invokes OpenRouter and returns generated text response."""
        client = self.get_chat_model(**kwargs)
        try:
            response = await client.ainvoke(messages)
            content = response.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
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
        """Invokes OpenRouter with structured output enforced to target Pydantic schema."""
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
        Translates provider and OpenAI/HTTP errors into standardized AIServiceException types.
        Prevents leaking API keys or internal stack traces.
        """
        if isinstance(exc, AIServiceException):
            return exc

        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        # 1. Authentication errors (401, invalid key)
        if (
            "401" in exc_str
            or "unauthorized" in exc_str
            or "authentication" in exc_type
            or "invalid_api_key" in exc_str
            or "api key not valid" in exc_str
            or "invalid api key" in exc_str
            or "user not found" in exc_str
        ):
            return AIAuthenticationException(
                "OpenRouter authentication failed. Verify that OPENROUTER_API_KEY is valid.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 2. Rate limit / Quota errors (429, insufficient credits)
        if (
            "429" in exc_str
            or "ratelimit" in exc_type
            or "rate limit" in exc_str
            or "quota" in exc_str
            or "credits" in exc_str
            or "insufficient_quota" in exc_str
        ):
            return AIRateLimitException(
                "OpenRouter rate limit or quota exceeded. Please retry later.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 3. Timeout errors (504, timeout, deadline)
        if (
            "504" in exc_str
            or "timeout" in exc_type
            or "timeout" in exc_str
            or isinstance(exc, (asyncio.TimeoutError, TimeoutError))
            or "timed out" in exc_str
        ):
            return AITimeoutException(
                f"OpenRouter request exceeded timeout threshold ({self.settings.AI_TIMEOUT_SECONDS}s).",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 4. Service Unavailable (503, model unavailable)
        if (
            "503" in exc_str
            or "unavailable" in exc_type
            or "unavailable" in exc_str
            or "service unavailable" in exc_str
            or "overloaded" in exc_str
        ):
            return AIProviderException(
                f"OpenRouter model '{self.model_name}' is currently unavailable (503 Service Unavailable). Please retry shortly.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 5. Model not found (404)
        if (
            "404" in exc_str
            or "notfound" in exc_type
            or "not found" in exc_str
            or "does not exist" in exc_str
        ):
            return AIProviderException(
                f"Configured OpenRouter model '{self.model_name}' was not found or is unsupported.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 6. General provider error (502 / internal / unexpected)
        return AIProviderException(
            f"OpenRouter service error: {type(exc).__name__}",
            provider=self.provider_name,
            original_exception=exc,
        )

