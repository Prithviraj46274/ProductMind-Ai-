"""
ProductMind AI — Product Planning Agent Endpoints
Provides authenticated endpoints for generating comprehensive product plans, PRDs,
user stories with acceptance criteria, retrieving plans, and managing the human review lifecycle.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.agents.product_planning import (
    ProductPlanningAgent,
    ProductPlanningService,
    GenerateProductPlanRequest,
    GeneratePRDRequest,
    GenerateUserStoriesRequest,
    ReviewPlanRequest,
    ProductPlanResponse,
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
    get_prd_repository,
    get_feature_group_repository,
    get_prioritization_scenario_repository,
    get_feedback_repository,
    get_workspace_repository,
    get_workspace_membership_repository,
)
from app.models.auth import User
from app.repositories import (
    PRDRepository,
    FeatureGroupRepository,
    PrioritizationScenarioRepository,
    FeedbackRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.api.planning_ai")

router = APIRouter(prefix="/ai/planning", tags=["AI Product Planning"])


def get_product_planning_service(
    llm_service: LLMService = Depends(get_llm_service),
    prd_repo: PRDRepository = Depends(get_prd_repository),
    feature_group_repo: FeatureGroupRepository = Depends(get_feature_group_repository),
    prioritization_repo: PrioritizationScenarioRepository = Depends(get_prioritization_scenario_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
) -> ProductPlanningService:
    """Dependency injector for ProductPlanningService."""
    agent = ProductPlanningAgent(llm_service=llm_service)
    return ProductPlanningService(
        agent=agent,
        prd_repo=prd_repo,
        feature_group_repo=feature_group_repo,
        prioritization_repo=prioritization_repo,
        feedback_repo=feedback_repo,
        workspace_repo=workspace_repo,
        membership_repo=membership_repo,
    )


@router.post(
    "/generate",
    status_code=status.HTTP_200_OK,
    summary="Generate Comprehensive Product Plan",
    description="Transforms a prioritized feature group into a structured PRD, user stories, acceptance criteria, technical requirements, success metrics, and roadmap.",
    response_model=ProductPlanResponse,
)
async def generate_product_plan(
    payload: GenerateProductPlanRequest,
    current_user: User = Depends(get_current_user),
    service: ProductPlanningService = Depends(get_product_planning_service),
) -> ProductPlanResponse:
    """
    Generates a full product plan:
    - Enforces workspace security.
    - Grounds requirements in original customer feedback quotes and pain points.
    - Incorporates prior prioritization scores and rationale when available.
    - Generates user stories with Given-When-Then acceptance criteria.
    - Suggests technical specifications labeled for engineering review.
    - Sets baseline metrics to null without fabricating figures.
    - Persists document in 'pending_review' state to the PRD collection.
    """
    try:
        return await service.generate_plan(
            request=payload,
            user=current_user,
        )
    except HTTPException:
        raise
    except AIAuthenticationException as exc:
        logger.error("Planning AI authentication failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AI provider authentication failed: invalid or expired credentials.",
        )
    except AIRateLimitException as exc:
        logger.warning("Planning AI rate limit hit: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit reached. Please retry in a few moments.",
        )
    except AITimeoutException as exc:
        logger.warning("Planning AI timeout: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI model request timed out during product plan generation.",
        )
    except (AIConfigurationException, AIProviderException, AIServiceException) as exc:
        logger.error("Planning AI provider/service exception: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model service failure: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error during product plan generation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during product plan generation.",
        )


@router.post(
    "/generate-prd",
    status_code=status.HTTP_200_OK,
    summary="Generate or Regenerate PRD Only",
    description="Generates or updates specifically the Product Requirements Document section of a product plan.",
    response_model=ProductPlanResponse,
)
async def generate_prd(
    payload: GeneratePRDRequest,
    current_user: User = Depends(get_current_user),
    service: ProductPlanningService = Depends(get_product_planning_service),
) -> ProductPlanResponse:
    """Generates or updates the PRD document section for a feature group."""
    try:
        return await service.generate_prd_only(
            request=payload,
            user=current_user,
        )
    except HTTPException:
        raise
    except AIAuthenticationException as exc:
        logger.error("Planning AI auth error: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AI authentication failed.")
    except AIRateLimitException as exc:
        logger.warning("Planning AI rate limit: %s", exc)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI rate limit reached.")
    except AITimeoutException as exc:
        logger.warning("Planning AI timeout: %s", exc)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="AI request timed out.")
    except (AIConfigurationException, AIProviderException, AIServiceException) as exc:
        logger.error("Planning AI provider/service error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI service failure: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error during PRD generation: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generating PRD.")


@router.post(
    "/generate-user-stories",
    status_code=status.HTTP_200_OK,
    summary="Generate or Regenerate User Stories",
    description="Generates or updates user stories and Given-When-Then acceptance criteria for a feature group.",
    response_model=ProductPlanResponse,
)
async def generate_user_stories(
    payload: GenerateUserStoriesRequest,
    current_user: User = Depends(get_current_user),
    service: ProductPlanningService = Depends(get_product_planning_service),
) -> ProductPlanResponse:
    """Generates or updates user stories and acceptance criteria."""
    try:
        return await service.generate_user_stories_only(
            request=payload,
            user=current_user,
        )
    except HTTPException:
        raise
    except AIAuthenticationException as exc:
        logger.error("Planning AI auth error: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AI authentication failed.")
    except AIRateLimitException as exc:
        logger.warning("Planning AI rate limit: %s", exc)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="AI rate limit reached.")
    except AITimeoutException as exc:
        logger.warning("Planning AI timeout: %s", exc)
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="AI request timed out.")
    except (AIConfigurationException, AIProviderException, AIServiceException) as exc:
        logger.error("Planning AI provider/service error: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI service failure: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error during user story generation: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generating user stories.")


@router.get(
    "/{planning_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Product Plan by ID",
    description="Retrieves a stored product planning document by its PRD ID.",
    response_model=ProductPlanResponse,
)
async def get_product_plan(
    planning_id: str,
    workspace_id: Optional[str] = Query(None, description="Optional workspace ID verification"),
    current_user: User = Depends(get_current_user),
    service: ProductPlanningService = Depends(get_product_planning_service),
) -> ProductPlanResponse:
    """Retrieves a single product plan with all child sections and human review status."""
    try:
        return await service.get_plan_by_id(
            planning_id=planning_id,
            user=current_user,
            workspace_id=workspace_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error retrieving product plan '%s': %s", planning_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error retrieving plan.")


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="List Product Plans",
    description="Lists paginated product plans for a workspace with optional review status filtering.",
    response_model=List[ProductPlanResponse],
)
async def list_product_plans(
    workspace_id: str = Query(..., description="Target workspace ID"),
    status: Optional[str] = Query(None, description="Optional review status filter ('pending_review', 'approved', 'rejected', 'draft')"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    service: ProductPlanningService = Depends(get_product_planning_service),
) -> List[ProductPlanResponse]:
    """Retrieves stored product plans for the specified workspace."""
    try:
        return await service.list_plans(
            workspace_id=workspace_id,
            user=current_user,
            status_filter=status,
            limit=limit,
            skip=skip,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error listing product plans for workspace '%s': %s", workspace_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error listing plans.")


@router.patch(
    "/{planning_id}/review",
    status_code=status.HTTP_200_OK,
    summary="Update Plan Human Review Status",
    description="Enforces human product manager review: sets status to 'pending_review', 'approved', 'rejected', or 'draft'.",
    response_model=ProductPlanResponse,
)
async def update_plan_review_status(
    planning_id: str,
    payload: ReviewPlanRequest,
    current_user: User = Depends(get_current_user),
    service: ProductPlanningService = Depends(get_product_planning_service),
) -> ProductPlanResponse:
    """Updates the human review decision on a product planning document."""
    try:
        return await service.update_review_status(
            planning_id=planning_id,
            request=payload,
            user=current_user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error updating review status for plan '%s': %s", planning_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error updating review status.")

