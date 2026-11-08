"""
ProductMind AI — Feedback Intelligence Service
Orchestrates feedback retrieval, workspace permission authorization,
agent execution, database persistence, and batch processing.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import HTTPException, status

from app.ai.agents.feedback_intelligence.agent import FeedbackIntelligenceAgent
from app.ai.agents.feedback_intelligence.schemas import (
    FeedbackIntelligenceResult,
    FeedbackAnalysisResponse,
    BatchFeedbackItemResult,
    BatchFeedbackAnalysisResponse,
)
from app.core.enums import PlatformRole, MembershipStatus
from app.models.auth import User
from app.models.feedback import FeedbackItem
from app.repositories import (
    FeedbackRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)

logger = logging.getLogger("productmind.ai.service.feedback")


class FeedbackIntelligenceService:
    """
    Coordinates Feedback Intelligence Agent workflow with MongoDB repositories
    and strict workspace isolation rules.
    """

    def __init__(
        self,
        agent: Optional[FeedbackIntelligenceAgent] = None,
        feedback_repo: Optional[FeedbackRepository] = None,
        workspace_repo: Optional[WorkspaceRepository] = None,
        membership_repo: Optional[WorkspaceMembershipRepository] = None,
    ):
        self.agent = agent or FeedbackIntelligenceAgent()
        self.feedback_repo = feedback_repo
        self.workspace_repo = workspace_repo
        self.membership_repo = membership_repo

    async def verify_workspace_access(self, user: User, workspace_id: Any) -> None:
        """
        Enforces strict workspace authorization.
        Permits access if user is platform admin, workspace owner, or active member.
        Raises HTTP 403 Forbidden if user lacks workspace access.
        """
        if user.platform_role == PlatformRole.PLATFORM_ADMIN:
            return

        if self.workspace_repo is None or self.membership_repo is None:
            return

        ws_oid = ObjectId(str(workspace_id)) if not isinstance(workspace_id, ObjectId) else workspace_id
        workspace = await self.workspace_repo.find_by_id(ws_oid)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # Check workspace ownership
        if str(workspace.owner_id) == str(user.id):
            return

        # Check active membership
        membership = await self.membership_repo.find_membership(ws_oid, user.id)
        if not membership or membership.status != MembershipStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have active access to the workspace associated with this feedback item.",
            )

    async def analyze_feedback_item(
        self,
        feedback_id: str,
        user: User,
        force_reanalyze: bool = False,
    ) -> FeedbackAnalysisResponse:
        """
        Analyzes a single feedback item:
        1. Retrieves item by ID.
        2. Verifies user workspace permissions.
        3. Returns existing analysis if available and force_reanalyze is False.
        4. Executes Feedback Intelligence Agent.
        5. Persists analysis to database.
        6. Returns structured response with telemetry.
        """
        if not ObjectId.is_valid(feedback_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feedback ID format: '{feedback_id}'",
            )

        feedback = await self.feedback_repo.find_by_id(feedback_id)
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback item '{feedback_id}' not found",
            )

        await self.verify_workspace_access(user, feedback.workspace_id)

        # Check existing analysis if reanalysis is not forced
        if not force_reanalyze and feedback.ai_analysis:
            try:
                stored_analysis = FeedbackIntelligenceResult(**feedback.ai_analysis)
                metadata = feedback.ai_analysis.get("metadata", {})
                analyzed_at = feedback.analyzed_at or feedback.updated_at or datetime.now(timezone.utc)
                return FeedbackAnalysisResponse(
                    feedback_id=str(feedback.id),
                    workspace_id=str(feedback.workspace_id),
                    title=feedback.title,
                    analysis=stored_analysis,
                    metadata=metadata,
                    analyzed_at=analyzed_at,
                )
            except Exception as parse_err:
                logger.warning("Stored analysis for %s could not be parsed, reanalyzing: %s", feedback_id, parse_err)

        # Execute agent
        agent_input = {
            "feedback_id": str(feedback.id),
            "title": feedback.title,
            "description": feedback.description,
            "source_type": getattr(feedback.source_type, "value", str(feedback.source_type)),
            "customer_name": feedback.customer_name,
            "company_name": feedback.company_name,
        }

        exec_result = await self.agent.execute(agent_input)

        # Persist analysis
        analysis_data = exec_result.data.model_dump()
        metadata_dict = exec_result.metadata.model_dump()
        metadata_dict["completed_at"] = exec_result.metadata.completed_at.isoformat()
        metadata_dict["started_at"] = exec_result.metadata.started_at.isoformat()

        updated_doc = await self.feedback_repo.save_analysis(
            feedback_id=feedback.id,
            workspace_id=feedback.workspace_id,
            analysis_data=analysis_data,
            metadata_dict=metadata_dict,
        )

        if not updated_doc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to persist feedback intelligence analysis into database.",
            )

        return FeedbackAnalysisResponse(
            feedback_id=str(feedback.id),
            workspace_id=str(feedback.workspace_id),
            title=feedback.title,
            analysis=exec_result.data,
            metadata=exec_result.metadata.model_dump(),
            analyzed_at=exec_result.metadata.completed_at,
        )

    async def get_feedback_analysis(
        self,
        feedback_id: str,
        user: User,
    ) -> FeedbackAnalysisResponse:
        """
        Retrieves existing analysis for a feedback item without invoking the LLM.
        """
        if not ObjectId.is_valid(feedback_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feedback ID format: '{feedback_id}'",
            )

        feedback = await self.feedback_repo.find_by_id(feedback_id)
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feedback item '{feedback_id}' not found",
            )

        await self.verify_workspace_access(user, feedback.workspace_id)

        if not feedback.ai_analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No AI analysis found for feedback item '{feedback_id}'. Execute POST /analyze first.",
            )

        stored_analysis = FeedbackIntelligenceResult(**feedback.ai_analysis)
        metadata = feedback.ai_analysis.get("metadata", {})
        analyzed_at = feedback.analyzed_at or feedback.updated_at or datetime.now(timezone.utc)

        return FeedbackAnalysisResponse(
            feedback_id=str(feedback.id),
            workspace_id=str(feedback.workspace_id),
            title=feedback.title,
            analysis=stored_analysis,
            metadata=metadata,
            analyzed_at=analyzed_at,
        )

    async def analyze_batch(
        self,
        feedback_ids: List[str],
        user: User,
        force_reanalyze: bool = False,
        concurrency_limit: int = 3,
    ) -> BatchFeedbackAnalysisResponse:
        """
        Safely analyzes a batch of feedback items with bounded concurrency to respect provider rate limits.
        """
        semaphore = asyncio.Semaphore(concurrency_limit)

        async def analyze_single(fid: str) -> BatchFeedbackItemResult:
            async with semaphore:
                try:
                    resp = await self.analyze_feedback_item(fid, user, force_reanalyze=force_reanalyze)
                    return BatchFeedbackItemResult(
                        feedback_id=fid,
                        status="success",
                        analysis=resp.analysis,
                    )
                except HTTPException as http_err:
                    return BatchFeedbackItemResult(
                        feedback_id=fid,
                        status="error",
                        error=str(http_err.detail),
                    )
                except Exception as err:
                    return BatchFeedbackItemResult(
                        feedback_id=fid,
                        status="error",
                        error=f"Analysis failed: {type(err).__name__}",
                    )

        tasks = [analyze_single(fid) for fid in feedback_ids]
        results = await asyncio.gather(*tasks)

        successful = sum(1 for r in results if r.status == "success")
        failed = len(results) - successful

        return BatchFeedbackAnalysisResponse(
            total_requested=len(feedback_ids),
            successful=successful,
            failed=failed,
            results=results,
        )

