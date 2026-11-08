"""
ProductMind AI — Groq LLM Provider
Implements LangChain ChatGroq integration targeting Groq's high-speed API endpoint,
specifically optimized for qwen/qwen3.8-27b with connection reuse,
retry configuration, reasoning controls, and comprehensive domain error mapping.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

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

logger = logging.getLogger("productmind.ai.groq")
T = TypeVar("T", bound=BaseModel)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider(BaseLLMProvider):
    """
    Production-grade LangChain integration for Groq endpoints.
    Uses ChatGroq to invoke fast inference models such as qwen/qwen3.8-27b.
    Manages client lifecycle, temperature/token limits, reasoning visibility,
    and robust exception mapping.
    """

    def __init__(self, settings: Optional[AISettings] = None):
        self.settings: AISettings = settings or ai_settings
        self._cached_client: Optional[ChatGroq] = None

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self.settings.AI_MODEL

    @property
    def api_base_url(self) -> str:
        return GROQ_BASE_URL

    def get_chat_model(
        self,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        reasoning_format: Optional[str] = "hidden",
        reasoning_effort: Optional[str] = None,
        **kwargs: Any,
    ) -> ChatGroq:
        """
        Retrieves an initialized ChatGroq instance configured for Groq.
        Reuses cached instance if using default parameters.
        Default reasoning_format='hidden' guarantees internal reasoning traces
        are never exposed to caller endpoints.
        """
        # Validate that credentials are present before attempting initialization
        self.settings.validate_for_execution()

        # Check if custom parameters were provided
        has_custom_params = any(
            p is not None for p in [temperature, max_output_tokens, timeout, max_retries, reasoning_effort]
        ) or reasoning_format != "hidden" or bool(kwargs)

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

        chat_kwargs: Dict[str, Any] = {
            "model": self.settings.AI_MODEL,
            "groq_api_key": self.settings.GROQ_API_KEY,
            "temperature": resolved_temperature,
            "max_tokens": resolved_max_tokens,
            "request_timeout": resolved_timeout,
            "max_retries": resolved_max_retries,
        }

        # Apply reasoning format if supported by model/client
        if reasoning_format:
            chat_kwargs["reasoning_format"] = reasoning_format
        if reasoning_effort:
            chat_kwargs["reasoning_effort"] = reasoning_effort

        # Merge any additional client kwargs
        chat_kwargs.update(kwargs)

        try:
            client = ChatGroq(**chat_kwargs)

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
        """Invokes Groq and returns sanitized generated text response."""
        client = self.get_chat_model(**kwargs)
        try:
            response = await client.ainvoke(messages)
            content = response.content
            raw_text = ""
            if isinstance(content, str):
                raw_text = content
            elif isinstance(content, list):
                raw_text = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            else:
                raw_text = str(content)

            # Strip any internal reasoning tokens if present (<think>...</think>)
            cleaned_text = re.sub(r"<think>[\s\S]*?</think>", "", raw_text).strip()
            return cleaned_text if cleaned_text else raw_text.strip()
        except Exception as exc:
            raise self._map_exception(exc)

    async def ainvoke_structured(
        self,
        schema: Type[T],
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> T:
        """Invokes Groq with structured output enforced to target Pydantic schema."""
        client = self.get_chat_model(**kwargs)
        try:
            # Prefer json_schema mode to prevent tool name hallucination on reasoning models like Qwen
            try:
                structured_chain = client.with_structured_output(schema, method="json_schema")
            except (NotImplementedError, ValueError):
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
        Translates provider and Groq/HTTP errors into standardized AIServiceException types.
        Prevents leaking API keys or internal stack traces.
        """
        if isinstance(exc, AIServiceException):
            return exc

        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        # 1. Authentication errors (401, invalid API key)
        if (
            "401" in exc_str
            or "unauthorized" in exc_str
            or "invalid_api_key" in exc_str
            or "invalid api key" in exc_str
            or "authentication" in exc_type
        ):
            return AIAuthenticationException(
                "Groq authentication failed. Verify that GROQ_API_KEY is valid.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 2. Rate limit / Quota errors (429, TPM/RPM limits)
        if (
            "429" in exc_str
            or "ratelimit" in exc_type
            or "rate limit" in exc_str
            or "quota" in exc_str
            or "tpm" in exc_str
            or "rpm" in exc_str
        ):
            return AIRateLimitException(
                "Groq rate limit or token quota exceeded. Please retry later.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 3. Timeout errors (504, request timeout)
        if (
            "504" in exc_str
            or "timeout" in exc_type
            or "timeout" in exc_str
            or isinstance(exc, (asyncio.TimeoutError, TimeoutError))
            or "timed out" in exc_str
        ):
            return AITimeoutException(
                f"Groq request exceeded timeout threshold ({self.settings.AI_TIMEOUT_SECONDS}s).",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 4. Service Unavailable (503, service overloaded)
        if (
            "503" in exc_str
            or "unavailable" in exc_type
            or "unavailable" in exc_str
            or "overloaded" in exc_str
        ):
            return AIProviderException(
                f"Groq model '{self.model_name}' is currently unavailable (503 Service Unavailable). Please retry shortly.",
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
                f"Configured Groq model '{self.model_name}' was not found or is unsupported.",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 6. General provider error (502 / unexpected)
        return AIProviderException(
            f"Groq service error: {type(exc).__name__}",
            provider=self.provider_name,
            original_exception=exc,
        )
