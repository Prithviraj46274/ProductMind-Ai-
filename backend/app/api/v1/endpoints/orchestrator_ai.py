"""
ProductMind AI — Central AI Orchestrator Endpoints
Provides authenticated endpoints for executing full multi-agent pipelines,
partial targeted workflows, run state retrieval, and health diagnostics.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.agents.feedback_intelligence import FeedbackIntelligenceService
from app.ai.agents.feature_intelligence import FeatureIntelligenceService
from app.ai.agents.prioritization import PrioritizationService
from app.ai.agents.product_planning import ProductPlanningService
from app.ai.exceptions import (
    AIServiceException,
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
)
from app.ai.orchestrator.exceptions import (
    OrchestratorAuthorizationException,
    OrchestratorDependencyException,
    OrchestratorException,
    OrchestratorStageExecutionException,
    OrchestratorValidationException,
)
from app.ai.orchestrator.orchestrator import AIOrchestrator
from app.ai.orchestrator.pipeline import PipelineCoordinator
from app.ai.orchestrator.schemas import (
    OrchestratorHealthResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)
from app.ai.orchestrator.state import (
    OrchestratorRunStore,
    get_orchestrator_run_store,
)
from app.api.dependencies import (
    get_current_user,
    get_feedback_repository,
    get_feature_group_repository,
    get_prioritization_scenario_repository,
    get_prd_repository,
    get_workspace_repository,
    get_workspace_membership_repository,
)
from app.api.v1.endpoints.feedback_ai import get_feedback_intelligence_service
from app.api.v1.endpoints.feature_ai import get_feature_intelligence_service
from app.api.v1.endpoints.prioritization_ai import get_prioritization_service
from app.api.v1.endpoints.planning_ai import get_product_planning_service
from app.models.auth import User
from app.repositories import (
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.api.orchestrator_ai")

router = APIRouter(prefix="/ai/orchestrator", tags=["AI Orchestrator"])


def get_ai_orchestrator(
    feedback_service: FeedbackIntelligenceService = Depends(get_feedback_intelligence_service),
    feature_service: FeatureIntelligenceService = Depends(get_feature_intelligence_service),
    prioritization_service: PrioritizationService = Depends(get_prioritization_service),
    planning_service: ProductPlanningService = Depends(get_product_planning_service),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    run_store: OrchestratorRunStore = Depends(get_orchestrator_run_store),
) -> AIOrchestrator:
    """Dependency injector constructing the AIOrchestrator with full coordinator wiring."""
    coordinator = PipelineCoordinator(
        feedback_service=feedback_service,
        feature_service=feature_service,
        prioritization_service=prioritization_service,
        planning_service=planning_service,
        inter_stage_delay_seconds=2.0,
    )
    return AIOrchestrator(
        coordinator=coordinator,
        workspace_repo=workspace_repo,
        membership_repo=membership_repo,
        run_store=run_store,
    )


@router.post(
    "/run",
    status_code=status.HTTP_200_OK,
    summary="Execute AI Orchestrator Pipeline",
    description="Coordinates multi-agent workflows (full 4-stage pipeline or targeted partial stages) with dependency validation, workspace isolation, and state management.",
    response_model=OrchestratorResponse,
)
async def run_pipeline(
    payload: OrchestratorRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> OrchestratorResponse:
    """
    Executes an orchestration pipeline:
    - Mode A: Full Pipeline (Feedback -> Feature Grouping -> Prioritization -> Product Planning)
    - Mode B: Partial Pipeline (Targeted execution of specified stages with prerequisite validation)
    """
    try:
        return await orchestrator.run_pipeline(request=payload, user=current_user)
    except HTTPException:
        raise
    except OrchestratorAuthorizationException as exc:
        logger.warning("Workspace authorization denied in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except OrchestratorValidationException as exc:
        logger.warning("Validation error in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except OrchestratorDependencyException as exc:
        logger.warning("Dependency requirement error in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except AIAuthenticationException as exc:
        logger.error("AI provider authentication failure in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AI provider authentication failed: invalid or expired credentials.",
        )
    except AIRateLimitException as exc:
        logger.warning("AI provider rate limit hit in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit reached. Please retry in a few moments.",
        )
    except AITimeoutException as exc:
        logger.warning("AI provider timeout in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI model request timed out during orchestration execution.",
        )
    except (AIConfigurationException, AIProviderException) as exc:
        logger.error("AI provider exception in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI model service failure: {exc}",
        )
    except Exception as exc:
        logger.exception("Unexpected error in orchestrator: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during pipeline orchestration.",
        )


@router.get(
    "/runs/{run_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Orchestrator Run Execution State",
    description="Retrieves the detailed execution status, timings, and stage results of an orchestration run by its run ID.",
    response_model=OrchestratorResponse,
)
async def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> OrchestratorResponse:
    """Retrieves an orchestrator run by ID, enforcing workspace authorization."""
    try:
        response = await orchestrator.get_run_by_id(run_id=run_id, user=current_user)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orchestration run '{run_id}' not found.",
            )
        return response
    except HTTPException:
        raise
    except OrchestratorAuthorizationException as exc:
        logger.warning("Unauthorized access to run %s: %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Error retrieving orchestrator run %s: %s", run_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving run state.",
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="AI Orchestrator Health and Capability Diagnostic",
    description="Returns operational health and readiness of the central orchestrator and all four underlying specialist agents.",
    response_model=OrchestratorHealthResponse,
)
async def orchestrator_health(
    orchestrator: AIOrchestrator = Depends(get_ai_orchestrator),
) -> OrchestratorHealthResponse:
    """Returns the operational health and specialist agent connectivity status."""
    try:
        return await orchestrator.get_health()
    except Exception as exc:
        logger.exception("Error checking orchestrator health: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orchestrator health.",
        )


# Direct /orchestrator prefix alias router supporting canonical /api/v1/orchestrator/* URIs
alias_router = APIRouter(prefix="/orchestrator", tags=["AI Orchestrator"])
alias_router.add_api_route(
    "/run",
    run_pipeline,
    methods=["POST"],
    status_code=status.HTTP_200_OK,
    summary="Execute AI Orchestrator Pipeline (Direct Alias)",
    description="Direct endpoint alias for /api/v1/orchestrator/run.",
    response_model=OrchestratorResponse,
)
alias_router.add_api_route(
    "/runs/{run_id}",
    get_run,
    methods=["GET"],
    status_code=status.HTTP_200_OK,
    summary="Retrieve Orchestrator Run Execution State (Direct Alias)",
    description="Direct endpoint alias for /api/v1/orchestrator/runs/{run_id}.",
    response_model=OrchestratorResponse,
)
alias_router.add_api_route(
    "/health",
    orchestrator_health,
    methods=["GET"],
    status_code=status.HTTP_200_OK,
    summary="AI Orchestrator Health and Capability Diagnostic (Direct Alias)",
    description="Direct endpoint alias for /api/v1/orchestrator/health.",
    response_model=OrchestratorHealthResponse,
)


