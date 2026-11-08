"""
ProductMind AI — Feature Intelligence Agent Endpoints
Provides authenticated endpoints for grouping feature requests, retrieving consolidated
feature groups, inspecting individual feature groups, and detecting duplicates.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.agents.feature_intelligence import (
    FeatureIntelligenceAgent,
    FeatureIntelligenceService,
    GroupFeaturesRequest,
    GroupFeaturesResponse,
    FeatureGroupResult,
    DuplicateDetectionRequest,
    DuplicateDetectionResponse,
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
    get_feature_group_repository,
    get_feedback_repository,
    get_workspace_repository,
    get_workspace_membership_repository,
)
from app.models.auth import User
from app.repositories import (
    FeatureGroupRepository,
    FeedbackRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.api.feature_ai")

router = APIRouter(prefix="/ai/features", tags=["AI Feature Intelligence"])


def get_feature_intelligence_service(
    llm_service: LLMService = Depends(get_llm_service),
    feature_group_repo: FeatureGroupRepository = Depends(get_feature_group_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
) -> FeatureIntelligenceService:
    """Dependency injector for FeatureIntelligenceService."""
    agent = FeatureIntelligenceAgent(llm_service=llm_service)
    return FeatureIntelligenceService(
        agent=agent,
        feature_group_repo=feature_group_repo,
        feedback_repo=feedback_repo,
        workspace_repo=workspace_repo,
        membership_repo=membership_repo,
    )


@router.post(
    "/group",
    status_code=status.HTTP_200_OK,
    summary="Group Feature Requests with AI",
    description="Analyzes eligible customer feedback requests to group semantically similar items, calculate demand, and persist feature intelligence.",
    response_model=GroupFeaturesResponse,
)
async def group_features(
    payload: GroupFeaturesRequest,
    current_user: User = Depends(get_current_user),
    service: FeatureIntelligenceService = Depends(get_feature_intelligence_service),
) -> GroupFeaturesResponse:
    """
    Groups feedback requests into consolidated product features:
    - Enforces workspace security.
    - Filters eligible feature requests (respecting Feedback Intelligence analysis).
    - Clusters semantically equivalent requests while separating related distinct features.
    - Aggregates demand metrics (requests, unique customers, sentiment, urgency) in Python.
    - Persists feature groups to MongoDB and links feedback items.
    """
    try:
        return await service.group_feature_requests(
            workspace_id=payload.workspace_id,
            user=current_user,
            feedback_ids=payload.feedback_ids,
            force_regroup=payload.force_regroup,
            confidence_threshold=payload.confidence_threshold,
            min_group_size=payload.min_group_size,
        )
    except HTTPException:
        raise
    except AIAuthenticationException as exc:
        logger.error("Feature grouping AI authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AI provider authentication failed: invalid or expired credentials.",
        )
    except AIRateLimitException as exc:
        logger.warning("Feature grouping AI rate limit hit: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit reached. Please retry in a few moments.",
        )
    except AITimeoutException as exc:
        logger.warning("Feature grouping AI timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI model request timed out during feature clustering.",
        )
    except (AIConfigurationException, AIProviderException) as exc:
        logger.error("Feature grouping AI provider exception: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model service failure: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error during feature grouping: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during feature grouping.",
        )


@router.get(
    "/groups",
    status_code=status.HTTP_200_OK,
    summary="List Consolidated Feature Groups",
    description="Retrieves persisted feature groups for a given workspace with optional status and count filters.",
    response_model=List[FeatureGroupResult],
)
async def list_feature_groups(
    workspace_id: str = Query(..., description="Target workspace ID"),
    grouping_status: Optional[str] = Query(None, description="Optional workflow status filter (suggested, approved, merged)"),
    min_request_count: Optional[int] = Query(None, ge=1, description="Minimum feedback request count"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: FeatureIntelligenceService = Depends(get_feature_intelligence_service),
) -> List[FeatureGroupResult]:
    """Retrieves consolidated feature groups for the specified workspace."""
    return await service.get_feature_groups(
        workspace_id=workspace_id,
        user=current_user,
        status=grouping_status,
        min_request_count=min_request_count,
        limit=limit,
        skip=skip,
    )


@router.get(
    "/groups/{group_id}",
    status_code=status.HTTP_200_OK,
    summary="Get Feature Group by ID",
    description="Retrieves a specific consolidated feature group by ID with full customer demand metrics and feedback references.",
    response_model=FeatureGroupResult,
)
async def get_feature_group(
    group_id: str,
    workspace_id: str = Query(..., description="Associated workspace ID"),
    current_user: User = Depends(get_current_user),
    service: FeatureIntelligenceService = Depends(get_feature_intelligence_service),
) -> FeatureGroupResult:
    """Retrieves an individual feature group by ID."""
    return await service.get_feature_group_by_id(
        group_id=group_id,
        workspace_id=workspace_id,
        user=current_user,
    )


@router.post(
    "/detect-duplicates",
    status_code=status.HTTP_200_OK,
    summary="Detect Duplicate Feature Requests",
    description="Evaluates feedback items for exact, near, and semantic duplication while separating related distinct features.",
    response_model=DuplicateDetectionResponse,
)
async def detect_duplicates(
    payload: DuplicateDetectionRequest,
    current_user: User = Depends(get_current_user),
    service: FeatureIntelligenceService = Depends(get_feature_intelligence_service),
) -> DuplicateDetectionResponse:
    """
    Evaluates candidate feature requests for duplicate relationships:
    - Identifies exact, near, and semantic duplicates.
    - Distinguishes related distinct capabilities (e.g. CSV vs Excel).
    - Returns actionable merge/separate recommendations.
    """
    try:
        return await service.detect_duplicates(
            workspace_id=payload.workspace_id,
            user=current_user,
            feedback_ids=payload.feedback_ids,
            target_feedback_id=payload.target_feedback_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during duplicate detection: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during duplicate detection: {exc}",
        )

