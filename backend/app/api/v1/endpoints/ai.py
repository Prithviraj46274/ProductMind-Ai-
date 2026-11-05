"""
ProductMind AI — AI Service Diagnostic Endpoints
Provides non-destructive health checks, active provider/model diagnostics,
and authenticated connectivity testing for the Gemini LLM foundation.
"""

import time
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.config import ai_settings
from app.ai.exceptions import (
    AIServiceException,
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
)
from app.ai.llm_service import LLMService, get_llm_service
from app.ai.schemas import AIHealthResponse, AITestRequest, AITestResponse
from app.api.dependencies import get_optional_current_user
from app.models.auth import User

logger = logging.getLogger("productmind.api.ai")
router = APIRouter(prefix="/ai", tags=["AI & LLM Diagnostics"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="AI Service Health & Configuration Diagnostic",
    description="Inspects active AI provider configuration and readiness without making external LLM calls. Never exposes API keys.",
    response_model=AIHealthResponse,
)
async def get_ai_health(
    llm_service: LLMService = Depends(get_llm_service),
) -> AIHealthResponse:
    """
    Returns sanitized status of the shared AI foundation.
    Does not consume provider quota or make network calls.
    """
    is_ready = llm_service.is_configured
    status_label = "ready" if is_ready else "unconfigured"

    return AIHealthResponse(
        status=status_label,
        provider=llm_service.provider_name,
        model=llm_service.model_name,
        is_configured=is_ready,
        temperature=llm_service.settings.AI_TEMPERATURE,
        max_output_tokens=llm_service.settings.AI_MAX_OUTPUT_TOKENS,
        timeout_seconds=llm_service.settings.AI_TIMEOUT_SECONDS,
        max_retries=llm_service.settings.AI_MAX_RETRIES,
    )


@router.post(
    "/test",
    status_code=status.HTTP_200_OK,
    summary="Test Gemini LLM Connectivity",
    description="Sends a lightweight test prompt to Google Gemini to verify end-to-end model connectivity and latency.",
    response_model=AITestResponse,
)
async def test_ai_connectivity(
    payload: Optional[AITestRequest] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> AITestResponse:
    """
    Executes a small test generation against Google Gemini.
    Tracks latency and maps provider errors to sanitized HTTP error responses.
    """
    if not llm_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured. Set GOOGLE_API_KEY in your environment.",
        )

    test_payload = payload or AITestRequest()
    prompt = test_payload.prompt or "Hello ProductMind AI! Confirm LLM foundation is operational."
    system_instruction = test_payload.system_instruction

    start_time = time.perf_counter()

    try:
        response_text = await llm_service.generate_text(
            prompt=prompt,
            system_instruction=system_instruction,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return AITestResponse(
            status="success",
            provider=llm_service.provider_name,
            model=llm_service.model_name,
            prompt=prompt,
            response=response_text,
            latency_ms=latency_ms,
        )

    except AIAuthenticationException as exc:
        logger.error("AI test authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AI provider authentication failed: invalid or expired API credentials.",
        )
    except AIRateLimitException as exc:
        logger.warning("AI test rate limited: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit or quota exceeded. Please retry later.",
        )
    except AITimeoutException as exc:
        logger.warning("AI test timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI model request timed out.",
        )
    except AIConfigurationException as exc:
        logger.error("AI test configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI configuration error: {exc.message}",
        )
    except AIProviderException as exc:
        logger.error("AI provider error: %s", exc)
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "503" in exc.message or "unavailable" in exc.message.lower()
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=status_code,
            detail=exc.message,
        )
    except AIServiceException as exc:
        logger.error("AI test service failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model service encountered an unexpected error.",
        )
    except Exception as exc:
        logger.exception("Unhandled error during AI test execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing AI diagnostic request.",
        )

