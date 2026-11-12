"""
ProductMind AI — Prioritization Agent Endpoints
Provides authenticated endpoints for evaluating feature groups, ranking features by composite score,
retrieving stored prioritization records, and inspecting prioritization results.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.agents.prioritization import (
    PrioritizationAgent,
    PrioritizationService,
    AnalyzePrioritizationRequest,
    AnalyzePrioritizationResponse,
    PrioritizationResult,
    RankPrioritizationRequest,
    RankPrioritizationResponse,
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
    get_prioritization_scenario_repository,
    get_feature_group_repository,
    get_feedback_repository,
    get_workspace_repository,
    get_workspace_membership_repository,
    get_analytics_rollup_repository,
)
from app.models.auth import User
from app.repositories import (
    AnalyticsDailyRollupRepository,
    PrioritizationScenarioRepository,
    FeatureGroupRepository,
    FeedbackRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.api.prioritization_ai")

router = APIRouter(prefix="/ai/prioritization", tags=["AI Prioritization"])


def get_prioritization_service(
    llm_service: LLMService = Depends(get_llm_service),
    prioritization_repo: PrioritizationScenarioRepository = Depends(get_prioritization_scenario_repository),
    feature_group_repo: FeatureGroupRepository = Depends(get_feature_group_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    analytics_rollup_repo: AnalyticsDailyRollupRepository = Depends(get_analytics_rollup_repository),
) -> PrioritizationService:
    """Dependency injector for PrioritizationService."""
    agent = PrioritizationAgent(llm_service=llm_service)
    return PrioritizationService(
        agent=agent,
        prioritization_repo=prioritization_repo,
        feature_group_repo=feature_group_repo,
        feedback_repo=feedback_repo,
        workspace_repo=workspace_repo,
        membership_repo=membership_repo,
        analytics_rollup_repo=analytics_rollup_repo,
    )


@router.post(
    "/analyze",
    status_code=status.HTTP_200_OK,
    summary="Analyze and Prioritize Feature Groups",
    description="Evaluates feature groups using customer demand, urgency, sentiment, usage impact, and LLM-assessed business impact and strategic alignment.",
    response_model=AnalyzePrioritizationResponse,
)
async def analyze_prioritization(
    payload: AnalyzePrioritizationRequest,
    current_user: User = Depends(get_current_user),
    service: PrioritizationService = Depends(get_prioritization_service),
) -> AnalyzePrioritizationResponse:
    """
    Analyzes and prioritizes feature groups:
    - Enforces workspace security.
    - Evaluates demand, urgency, and sentiment deterministically from feedback.
    - Incorporates product analytics when available, or reweights missing signals.
    - Evaluates qualitative business impact and strategic alignment via PrioritizationAgent.
    - Computes final composite score in Python (0-100 scale).
    - Persists results to MongoDB and returns ranked recommendations.
    """
    try:
        return await service.analyze_prioritization(
            request=payload,
            user=current_user,
        )
    except HTTPException:
        raise
    except AIAuthenticationException as exc:
        logger.error("Prioritization AI authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AI provider authentication failed: invalid or expired credentials.",
        )
    except AIRateLimitException as exc:
        logger.warning("Prioritization AI rate limit hit: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit reached. Please retry in a few moments.",
        )
    except AITimeoutException as exc:
        logger.warning("Prioritization AI timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI model request timed out during feature prioritization.",
        )
    except (AIConfigurationException, AIProviderException, AIServiceException) as exc:
        logger.error("Prioritization AI provider/service exception: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model service failure: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error during feature prioritization: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during feature prioritization.",
        )


@router.get(
    "/results",
    status_code=status.HTTP_200_OK,
    summary="List Prioritization Results",
    description="Retrieves persisted prioritization evaluations for a given workspace.",
    response_model=List[PrioritizationResult],
)
async def list_prioritization_results(
    workspace_id: str = Query(..., description="Target workspace ID"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: PrioritizationService = Depends(get_prioritization_service),
) -> List[PrioritizationResult]:
    """Retrieves stored prioritization results for the specified workspace."""
    try:
        return await service.get_prioritization_results(
            workspace_id=workspace_id,
            user=current_user,
            limit=limit,
            skip=skip,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error listing prioritization results: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving prioritization results.",
        )


@router.get(
    "/results/{result_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Prioritization Result by ID",
    description="Retrieves a specific prioritization evaluation by its record ID.",
    response_model=PrioritizationResult,
)
async def get_prioritization_result(
    result_id: str,
    workspace_id: str = Query(..., description="Target workspace ID"),
    current_user: User = Depends(get_current_user),
    service: PrioritizationService = Depends(get_prioritization_service),
) -> PrioritizationResult:
    """Retrieves an individual prioritization result."""
    try:
        return await service.get_prioritization_result_by_id(
            result_id=result_id,
            workspace_id=workspace_id,
            user=current_user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error retrieving prioritization result %s: %s", result_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the prioritization result.",
        )


@router.post(
    "/rank",
    status_code=status.HTTP_200_OK,
    summary="Rank Features by Priority Score",
    description="Ranks feature groups within a workspace by their deterministic composite priority score.",
    response_model=RankPrioritizationResponse,
)
async def rank_features(
    payload: RankPrioritizationRequest,
    current_user: User = Depends(get_current_user),
    service: PrioritizationService = Depends(get_prioritization_service),
) -> RankPrioritizationResponse:
    """
    Ranks feature groups:
    - Enforces workspace security.
    - Sorts features descending by final numerical score.
    - Supports optional minimum priority filter (e.g. Critical, High) and top-K limits.
    """
    try:
        return await service.rank_feature_groups(
            request=payload,
            user=current_user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error ranking features: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while ranking features.",
        )

