"""
ProductMind AI — Feedback Intelligence Agent Endpoints
Provides authenticated endpoints for analyzing customer feedback items,
retrieving stored intelligence, and bounded batch processing.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.agents.feedback_intelligence import (
    FeedbackIntelligenceAgent,
    FeedbackIntelligenceService,
    FeedbackAnalysisRequest,
    FeedbackAnalysisResponse,
    BatchFeedbackAnalysisRequest,
    BatchFeedbackAnalysisResponse,
)
from app.ai.exceptions import (
    AIServiceException,
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
)
from app.ai.llm_service import LLMService, get_llm_service
from app.api.dependencies import (
    get_current_user,
    get_feedback_repository,
    get_workspace_repository,
    get_workspace_membership_repository,
)
from app.models.auth import User
from app.repositories import (
    FeedbackRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.api.feedback_ai")

router = APIRouter(prefix="/ai/feedback", tags=["AI Feedback Intelligence"])


def get_feedback_intelligence_service(
    llm_service: LLMService = Depends(get_llm_service),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
) -> FeedbackIntelligenceService:
    """Dependency injector for FeedbackIntelligenceService."""
    agent = FeedbackIntelligenceAgent(llm_service=llm_service)
    return FeedbackIntelligenceService(
        agent=agent,
        feedback_repo=feedback_repo,
        workspace_repo=workspace_repo,
        membership_repo=membership_repo,
    )


@router.post(
    "/{feedback_id}/analyze",
    status_code=status.HTTP_200_OK,
    summary="Analyze Customer Feedback with AI",
    description="Invokes the Feedback Intelligence Agent to classify, evaluate sentiment, extract pain points, and recommend actions.",
    response_model=FeedbackAnalysisResponse,
)
async def analyze_feedback(
    feedback_id: str,
    payload: Optional[FeedbackAnalysisRequest] = None,
    current_user: User = Depends(get_current_user),
    service: FeedbackIntelligenceService = Depends(get_feedback_intelligence_service),
) -> FeedbackAnalysisResponse:
    """
    Analyzes an individual customer feedback item:
    - Authenticates user and validates active workspace access.
    - Executes the specialist Feedback Intelligence Agent.
    - Persists analysis to the database.
    - Returns structured output conforming to FeedbackIntelligenceResult.
    """
    force_reanalyze = payload.force_reanalyze if payload else False

    try:
        return await service.analyze_feedback_item(
            feedback_id=feedback_id,
            user=current_user,
            force_reanalyze=force_reanalyze,
        )
    except HTTPException:
        raise
    except AIAuthenticationException as exc:
        logger.error("Feedback analysis authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AI provider authentication failed: invalid or expired credentials.",
        )
    except AIRateLimitException as exc:
        logger.warning("Feedback analysis rate limited: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit or quota exceeded. Please retry later.",
        )
    except AITimeoutException as exc:
        logger.warning("Feedback analysis timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI model request timed out during feedback analysis.",
        )
    except AIConfigurationException as exc:
        logger.error("Feedback analysis configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service configuration error: {exc.message}",
        )
    except AIProviderException as exc:
        logger.error("Feedback analysis provider error: %s", exc)
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
        logger.error("Feedback analysis service failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model service encountered an unexpected error during feedback analysis.",
        )
    except Exception as exc:
        logger.exception("Unexpected error during feedback analysis execution")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing feedback analysis.",
        )


@router.get(
    "/{feedback_id}/analysis",
    status_code=status.HTTP_200_OK,
    summary="Get Stored Feedback Analysis",
    description="Retrieves existing intelligence analysis for a feedback item without consuming LLM quota.",
    response_model=FeedbackAnalysisResponse,
)
async def get_feedback_analysis(
    feedback_id: str,
    current_user: User = Depends(get_current_user),
    service: FeedbackIntelligenceService = Depends(get_feedback_intelligence_service),
) -> FeedbackAnalysisResponse:
    """
    Retrieves previously persisted feedback analysis.
    Verifies user has access to the feedback item's workspace.
    """
    return await service.get_feedback_analysis(feedback_id=feedback_id, user=current_user)


@router.post(
    "/analyze-batch",
    status_code=status.HTTP_200_OK,
    summary="Batch Analyze Feedback Items",
    description="Analyzes up to 10 feedback items with bounded concurrency to protect provider limits.",
    response_model=BatchFeedbackAnalysisResponse,
)
async def analyze_feedback_batch(
    payload: BatchFeedbackAnalysisRequest,
    current_user: User = Depends(get_current_user),
    service: FeedbackIntelligenceService = Depends(get_feedback_intelligence_service),
) -> BatchFeedbackAnalysisResponse:
    """
    Batch executes feedback intelligence with concurrency throttling:
    - Up to 10 items per request.
    - Concurrency limited to 3 concurrent model calls.
    - Returns per-item results and summary counts.
    """
    return await service.analyze_batch(
        feedback_ids=payload.feedback_ids,
        user=current_user,
        force_reanalyze=payload.force_reanalyze,
        concurrency_limit=3,
    )

