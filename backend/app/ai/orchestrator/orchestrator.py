"""
ProductMind AI — AI Orchestrator Service
Coordinates the end-to-end multi-agent pipeline, enforces strict workspace security,
manages run state, and provides health diagnostics for the specialist agent ecosystem.
"""

from datetime import datetime, timezone
import inspect
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from app.models.auth import User
from app.core.enums import PlatformRole, MembershipStatus
from app.database.collections import Collections
from app.ai.llm_service import LLMService, get_llm_service
from app.ai.orchestrator.schemas import (
    OrchestratorHealthResponse,
    OrchestratorRequest,
    OrchestratorResponse,
)
from app.ai.orchestrator.exceptions import (
    OrchestratorException,
    OrchestratorValidationException,
    OrchestratorDependencyException,
    OrchestratorAuthorizationException,
    OrchestratorStageExecutionException,
)
from app.ai.orchestrator.pipeline import PipelineCoordinator
from app.ai.orchestrator.state import (
    OrchestratorRunStore,
    PipelineExecutionState,
    get_orchestrator_run_store,
)
from app.repositories import WorkspaceRepository, WorkspaceMembershipRepository

logger = logging.getLogger("productmind.ai.orchestrator")


class AIOrchestrator:
    """
    Central orchestrator coordinating specialist agents:
    Feedback Intelligence -> Feature Intelligence -> Prioritization -> Product Planning.
    """

    def __init__(
        self,
        pipeline: Optional[PipelineCoordinator] = None,
        coordinator: Optional[PipelineCoordinator] = None,
        workspace_repo: Optional[WorkspaceRepository] = None,
        membership_repo: Optional[WorkspaceMembershipRepository] = None,
        run_store: Optional[OrchestratorRunStore] = None,
        llm_service: Optional[LLMService] = None,
        db: Optional[Any] = None,
    ):
        self.pipeline = pipeline or coordinator
        if not self.pipeline:
            raise ValueError("PipelineCoordinator must be provided to AIOrchestrator")
        self.workspace_repo = workspace_repo
        self.membership_repo = membership_repo
        self.run_store = run_store or get_orchestrator_run_store()
        self.llm_service = llm_service
        self.db = db
        self._indexes_ensured = False

    async def _ensure_run_indexes(self) -> None:
        if self.db is None or self._indexes_ensured:
            return
        try:
            col = self.db[Collections.ORCHESTRATOR_RUNS]
            await col.create_index("run_id", unique=True, name="idx_orchestrator_run_id_unique")
            await col.create_index(
                [("workspace_id", 1), ("started_at", -1)],
                name="idx_orchestrator_ws_started",
            )
            self._indexes_ensured = True
        except Exception as exc:
            logger.warning("Failed to ensure orchestrator_runs indexes: %s", exc)

    async def _persist_run_to_db(self, response: OrchestratorResponse) -> None:
        """Persists an orchestrator execution record to MongoDB Atlas."""
        if self.db is None:
            return
        await self._ensure_run_indexes()
        payload = response.model_dump(mode="json")
        payload["updated_at"] = datetime.now(timezone.utc)
        await self.db[Collections.ORCHESTRATOR_RUNS].replace_one(
            {"run_id": response.run_id},
            payload,
            upsert=True,
        )

    async def _load_run_from_db(self, run_id: str) -> Optional[OrchestratorResponse]:
        """Loads an orchestrator execution record from MongoDB Atlas by run_id."""
        if self.db is None:
            return None
        doc = await self.db[Collections.ORCHESTRATOR_RUNS].find_one({"run_id": run_id})
        if not doc:
            return None
        doc.pop("_id", None)
        doc.pop("updated_at", None)
        return OrchestratorResponse.model_validate(doc)

    async def verify_workspace_access(self, user: User, workspace_id: Any) -> None:
        """
        Enforces strict multi-tenant workspace isolation.
        Access is granted if user is platform admin, workspace owner, or active member.
        """
        if getattr(user, "platform_role", None) == PlatformRole.PLATFORM_ADMIN:
            return

        if self.workspace_repo is None or self.membership_repo is None:
            return

        if not ObjectId.is_valid(str(workspace_id)):
            raise OrchestratorValidationException(f"Invalid workspace ID format: '{workspace_id}'")
        ws_oid = ObjectId(str(workspace_id))

        # Check find_by_id or get_by_id
        find_fn = getattr(self.workspace_repo, "find_by_id", None) or getattr(self.workspace_repo, "get_by_id", None)
        if find_fn:
            res = find_fn(ws_oid)
            workspace = await res if inspect.isawaitable(res) else res
        else:
            workspace = None

        if not workspace:
            raise OrchestratorAuthorizationException(f"Workspace '{workspace_id}' not found")

        # Owner check
        if hasattr(workspace, "owner_id") and str(workspace.owner_id) == str(user.id):
            return

        # Active membership check
        mem_fn = (
            getattr(self.membership_repo, "find_by_workspace_and_user", None)
            or getattr(self.membership_repo, "find_membership", None)
            or getattr(self.membership_repo, "get_user_membership", None)
        )
        if mem_fn:
            res = mem_fn(ws_oid, user.id)
            membership = await res if inspect.isawaitable(res) else res
        else:
            membership = None

        if not membership:
            raise OrchestratorAuthorizationException(f"User is not a member of workspace '{workspace_id}'")

        status_val = getattr(membership, "status", None)
        if status_val and status_val != MembershipStatus.ACTIVE and status_val != "active":
            raise OrchestratorAuthorizationException(f"Membership is not active in workspace '{workspace_id}'")

    async def run_pipeline(
        self,
        request: OrchestratorRequest,
        user: User,
    ) -> OrchestratorResponse:
        """
        Validates, coordinates, and executes an AI orchestration workflow.
        """
        # 1. Workspace Security Verification
        await self.verify_workspace_access(user, request.workspace_id)
        ws_oid = ObjectId(request.workspace_id)

        # 2. Resolve target stages
        stages_to_run = self.pipeline.resolve_stages_to_run(request)

        # 3. Validate stage prerequisites & dependencies
        await self.pipeline.validate_dependencies(stages_to_run, request, ws_oid)

        # 4. Initialize Execution State
        state = PipelineExecutionState(
            workspace_id=request.workspace_id,
            mode=request.mode,
            stages_to_run=stages_to_run,
        )

        # Add provider metadata
        if self.llm_service:
            settings = self.llm_service.settings
            state.execution_metadata["provider"] = getattr(settings, "AI_PROVIDER", getattr(settings, "provider", "groq"))
            state.execution_metadata["model"] = getattr(settings, "AI_MODEL", getattr(settings, "model", "qwen/qwen3.8-27b"))

        # 5. Execute Pipeline Stages
        response = await self.pipeline.execute_pipeline(
            request=request,
            user=user,
            state=state,
        )

        # 6. Persist Run Result in MongoDB Atlas + in-process cache
        await self._persist_run_to_db(response)
        self.run_store.save_run(response)

        return response

    async def get_run_by_id(
        self,
        run_id: str,
        user: User,
    ) -> OrchestratorResponse:
        """
        Retrieves an orchestration run by ID (from memory cache or MongoDB Atlas)
        after verifying workspace access.
        """
        run = self.run_store.get_run(run_id)
        if not run and self.db is not None:
            run = await self._load_run_from_db(run_id)
            if run:
                self.run_store.save_run(run)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Orchestration run '{run_id}' not found",
            )

        # Enforce workspace security on retrieved run
        await self.verify_workspace_access(user, run.workspace_id)
        return run

    async def get_health(self) -> OrchestratorHealthResponse:
        """
        Reports operational health of the orchestrator and the 4 specialist agents.
        """
        service = self.llm_service or get_llm_service()
        settings = service.settings

        # Verify operational status of agents
        feedback_ok = hasattr(self.pipeline.feedback_service, "agent") and self.pipeline.feedback_service.agent is not None
        feature_ok = hasattr(self.pipeline.feature_service, "agent") and self.pipeline.feature_service.agent is not None
        prioritization_ok = hasattr(self.pipeline.prioritization_service, "agent") and self.pipeline.prioritization_service.agent is not None
        planning_ok = hasattr(self.pipeline.planning_service, "agent") and self.pipeline.planning_service.agent is not None

        all_ok = feedback_ok and feature_ok and prioritization_ok and planning_ok
        health_status = "healthy" if all_ok and service.is_configured else "degraded"

        agent_details = [
            {"agent": "Feedback Intelligence", "status": "healthy" if feedback_ok else "unhealthy"},
            {"agent": "Feature Intelligence", "status": "healthy" if feature_ok else "unhealthy"},
            {"agent": "Prioritization", "status": "healthy" if prioritization_ok else "unhealthy"},
            {"agent": "Product Planning", "status": "healthy" if planning_ok else "unhealthy"},
        ]

        active_count = self.run_store.size() if hasattr(self.run_store, "size") else len(getattr(self.run_store, "_runs", {}))

        provider_val = getattr(settings, "AI_PROVIDER", getattr(settings, "provider", "groq"))
        model_val = getattr(settings, "AI_MODEL", getattr(settings, "model", "qwen/qwen3.8-27b"))

        return OrchestratorHealthResponse(
            status=health_status,
            healthy=all_ok,
            provider=provider_val,
            model=model_val,
            agents_available={
                "feedback_intelligence": feedback_ok,
                "feature_intelligence": feature_ok,
                "prioritization": prioritization_ok,
                "product_planning": planning_ok,
            },
            specialist_agents=agent_details,
            active_runs_cached=active_count,
            uptime_seconds=0.0,
            timestamp=datetime.now(timezone.utc),
        )
