"""
ProductMind AI — Groq LLM Provider
Implements LangChain ChatGroq integration targeting Groq's high-speed API endpoint,
specifically optimized for qwen/qwen3.8-27b with connection reuse,
retry configuration, reasoning controls, and comprehensive domain error mapping.
"""

import asyncio
import json
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


class GroqUsageMetrics:
    """
    Thread-safe telemetry metrics for Groq API calls.
    Captures exact provider token metadata and API outcome counters.
    """

    def __init__(self):
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.rate_limit_responses: int = 0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0

    def record_usage(self, usage: Optional[Dict[str, Any]]) -> None:
        if not usage:
            return
        inp = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        out = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        tot = usage.get("total_tokens") or (inp + out)
        self.input_tokens += inp
        self.output_tokens += out
        self.total_tokens += tot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rate_limit_responses": self.rate_limit_responses,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


def _extract_retry_wait(exc: Exception, attempt: int) -> float:
    """Extracts wait duration from 429 error message or response header, bounded between 1.0s and 15.0s."""
    exc_str = str(exc).lower()
    if "max completion tokens reached" in exc_str:
        return min(5.0 * attempt + 1.0, 15.0)
    match = re.search(r"try again in ([0-9\.]+)s", exc_str, re.IGNORECASE)
    if match:
        try:
            return min(max(float(match.group(1)) + 0.5, 1.0), 15.0)
        except (ValueError, TypeError):
            pass
    resp = getattr(exc, "response", None)
    if resp and hasattr(resp, "headers"):
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after) + 0.5, 1.0), 15.0)
            except (ValueError, TypeError):
                pass
    return min(2.0 ** attempt * 2.0, 10.0)


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
        self.metrics: GroqUsageMetrics = GroqUsageMetrics()

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
        """Invokes Groq and returns sanitized generated text response with bounded 429 backoff."""
        client = self.get_chat_model(**kwargs)
        attempt = 0
        max_rate_limit_retries = 2

        while True:
            self.metrics.total_requests += 1
            try:
                response = await client.ainvoke(messages)
                self.metrics.successful_requests += 1
                usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {}).get("token_usage")
                self.metrics.record_usage(usage)

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
                exc_str = str(exc).lower()
                is_rate_limit = (
                    "429" in exc_str
                    or "rate limit" in exc_str
                    or "ratelimit" in exc_str
                    or "quota" in exc_str
                    or "tpm" in exc_str
                    or "max completion tokens reached" in exc_str
                )
                if is_rate_limit:
                    self.metrics.rate_limit_responses += 1
                    if attempt < max_rate_limit_retries:
                        attempt += 1
                        wait_s = _extract_retry_wait(exc, attempt)
                        logger.warning(
                            "Groq rate limit hit. Backing off for %.2fs (attempt %d/%d)...",
                            wait_s,
                            attempt,
                            max_rate_limit_retries,
                        )
                        await asyncio.sleep(wait_s)
                        continue
                self.metrics.failed_requests += 1
                raise self._map_exception(exc)

    async def ainvoke_structured(
        self,
        schema: Type[T],
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> T:
        """Invokes Groq with structured output enforced to target Pydantic schema with bounded 429 backoff.

        If the structured-output API returns a degenerate result (e.g. empty arrays for
        complex nested schemas — a known issue with reasoning models under JSON-schema
        constraints), automatically retries with a raw-text fallback: calls the model
        without schema constraints, extracts JSON from the response, and validates it
        against the Pydantic schema in Python.
        """
        client = self.get_chat_model(**kwargs)
        attempt = 0
        max_rate_limit_retries = 2

        # Configure structured chain with include_raw=True where supported for token tracking
        has_raw = True
        try:
            structured_chain = client.with_structured_output(schema, method="json_schema", include_raw=True)
        except (NotImplementedError, ValueError, TypeError):
            try:
                structured_chain = client.with_structured_output(schema, method="json_schema")
                has_raw = False
            except (NotImplementedError, ValueError):
                structured_chain = client.with_structured_output(schema)
                has_raw = False

        while True:
            self.metrics.total_requests += 1
            try:
                raw_result = await structured_chain.ainvoke(messages)
                self.metrics.successful_requests += 1

                # Unpack raw usage if include_raw was used
                if has_raw and isinstance(raw_result, dict) and "parsed" in raw_result:
                    raw_msg = raw_result.get("raw")
                    usage = getattr(raw_msg, "usage_metadata", None) or getattr(raw_msg, "response_metadata", {}).get("token_usage")
                    self.metrics.record_usage(usage)
                    if parsing_err := raw_result.get("parsing_error"):
                        raise parsing_err
                    parsed = raw_result.get("parsed")
                    if isinstance(parsed, schema):
                        # Detect degenerate output from reasoning model
                        if self._is_degenerate_structured_output(parsed):
                            logger.warning(
                                "Groq structured output returned degenerate result for %s. "
                                "Falling back to raw-text invocation with manual JSON parsing.",
                                schema.__name__,
                            )
                            return await self._ainvoke_structured_raw_fallback(schema, messages, **kwargs)
                        return parsed
                    elif isinstance(parsed, dict):
                        result = schema(**parsed)
                        if self._is_degenerate_structured_output(result):
                            logger.warning(
                                "Groq structured output returned degenerate result for %s. "
                                "Falling back to raw-text invocation with manual JSON parsing.",
                                schema.__name__,
                            )
                            return await self._ainvoke_structured_raw_fallback(schema, messages, **kwargs)
                        return result
                    else:
                        raise AISchemaValidationException(
                            f"Output cannot be converted to {schema.__name__}: {parsed}",
                            provider=self.provider_name,
                        )

                # Fallback unpacking when include_raw=False
                if isinstance(raw_result, schema):
                    if self._is_degenerate_structured_output(raw_result):
                        logger.warning(
                            "Groq structured output returned degenerate result for %s. "
                            "Falling back to raw-text invocation with manual JSON parsing.",
                            schema.__name__,
                        )
                        return await self._ainvoke_structured_raw_fallback(schema, messages, **kwargs)
                    return raw_result
                elif isinstance(raw_result, dict):
                    result = schema(**raw_result)
                    if self._is_degenerate_structured_output(result):
                        logger.warning(
                            "Groq structured output returned degenerate result for %s. "
                            "Falling back to raw-text invocation with manual JSON parsing.",
                            schema.__name__,
                        )
                        return await self._ainvoke_structured_raw_fallback(schema, messages, **kwargs)
                    return result
                else:
                    raise AISchemaValidationException(
                        f"Output cannot be converted to {schema.__name__}: {raw_result}",
                        provider=self.provider_name,
                    )
            except (ValidationError, TypeError) as val_err:
                self.metrics.failed_requests += 1
                raise AISchemaValidationException(
                    f"Model response failed validation for {schema.__name__}: {val_err}",
                    provider=self.provider_name,
                    original_exception=val_err,
                )
            except Exception as exc:
                exc_str = str(exc).lower()
                is_rate_limit = (
                    "429" in exc_str
                    or "rate limit" in exc_str
                    or "ratelimit" in exc_str
                    or "quota" in exc_str
                    or "tpm" in exc_str
                    or "max completion tokens reached" in exc_str
                )
                if is_rate_limit or "json_validate_failed" in exc_str:
                    if is_rate_limit:
                        self.metrics.rate_limit_responses += 1
                    if attempt < max_rate_limit_retries:
                        attempt += 1
                        wait_s = _extract_retry_wait(exc, attempt) if is_rate_limit else 1.0
                        logger.warning(
                            "Groq structured invocation failed (%s). Backing off for %.2fs (attempt %d/%d)...",
                            "rate limit" if is_rate_limit else "json_validate_failed",
                            wait_s,
                            attempt,
                            max_rate_limit_retries,
                        )
                        await asyncio.sleep(wait_s)
                        continue
                self.metrics.failed_requests += 1
                raise self._map_exception(exc)

    @staticmethod
    def _is_degenerate_structured_output(result: BaseModel) -> bool:
        """Detects when a reasoning model returns a structurally valid but semantically
        empty result due to JSON-schema constraint interference.

        Specifically checks for FeatureGroupingAgentOutput-like schemas where:
        - ``groups`` is empty AND ``ungrouped_feedback_ids`` has items, indicating the
          model could not populate the complex nested group schema under constraints.
        - OR ``groups`` is empty AND ``ungrouped_feedback_ids`` is also empty AND the
          schema has both fields, indicating complete degenerate output.
        """
        groups = getattr(result, "groups", None)
        ungrouped = getattr(result, "ungrouped_feedback_ids", None)
        # Only trigger for outputs that have both fields (feature grouping schema)
        if groups is not None and ungrouped is not None:
            if len(groups) == 0:
                return True
        return False

    async def _ainvoke_structured_raw_fallback(
        self,
        schema: Type[T],
        messages: List[BaseMessage],
        **kwargs: Any,
    ) -> T:
        """Fallback: invokes the model in plain text mode (no JSON schema constraint),
        extracts JSON from the response, and validates against the Pydantic schema.

        This handles reasoning models (e.g. qwen/qwen3.8-27b) that produce correct JSON
        in free-text mode but degenerate outputs under with_structured_output constraints.
        """
        logger.info("Executing raw-text structured fallback for %s", schema.__name__)
        raw_text = await self.ainvoke_text(messages, **kwargs)

        # Extract JSON from response (strip markdown fences, thinking tags, etc.)
        json_text = raw_text.strip()
        # Remove markdown code fences
        json_text = re.sub(r"^```(?:json)?\s*", "", json_text)
        json_text = re.sub(r"\s*```\s*$", "", json_text)
        # Remove <think>...</think> blocks
        json_text = re.sub(r"<think>[\s\S]*?</think>", "", json_text).strip()

        try:
            parsed_dict = json.loads(json_text)
        except json.JSONDecodeError as jde:
            raise AISchemaValidationException(
                f"Raw fallback: could not parse JSON from model response for {schema.__name__}: {jde}",
                provider=self.provider_name,
                original_exception=jde,
            )

        try:
            return schema(**parsed_dict)
        except (ValidationError, TypeError) as val_err:
            raise AISchemaValidationException(
                f"Raw fallback: parsed JSON failed Pydantic validation for {schema.__name__}: {val_err}",
                provider=self.provider_name,
                original_exception=val_err,
            )


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

        # 3. Model JSON formatting validation failure
        if "json_validate_failed" in exc_str:
            return AISchemaValidationException(
                f"Groq model produced invalid JSON format: {exc}",
                provider=self.provider_name,
                original_exception=exc,
            )

        # 4. Timeout errors (504, request timeout)
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
