"""
ProductMind AI — AI Orchestrator Domain Schemas
Defines request, response, stage status, execution telemetry, and health models
for multi-agent pipeline coordination.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.ai.agents.product_planning.schemas import ProductStrategicContext


class PipelineMode(str, Enum):
    FULL = "full"
    PARTIAL = "partial"


class PipelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class StageType(str, Enum):
    FEEDBACK_INTELLIGENCE = "feedback_intelligence"
    FEATURE_INTELLIGENCE = "feature_intelligence"
    PRIORITIZATION = "prioritization"
    PRODUCT_PLANNING = "product_planning"


class StageResult(BaseModel):
    """Execution status and output telemetry for an individual pipeline stage."""
    model_config = ConfigDict(extra="ignore")

    stage: StageType = Field(..., description="Pipeline stage identifier")
    status: StageStatus = Field(default=StageStatus.PENDING, description="Execution status of this stage")
    started_at: Optional[datetime] = Field(default=None, description="Stage execution start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Stage completion timestamp")
    duration_ms: Optional[float] = Field(default=None, description="Stage duration in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if stage failed")
    warning: Optional[str] = Field(default=None, description="Warning or notice for stage execution")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Stage-specific execution telemetry")

    @property
    def error_message(self) -> Optional[str]:
        return self.error

    @property
    def output(self) -> Optional[Dict[str, Any]]:
        return self.metadata


class OrchestratorRequest(BaseModel):
    """Payload to initiate a full or partial AI orchestration run."""
    model_config = ConfigDict(extra="ignore")

    workspace_id: str = Field(..., description="Target workspace ID")
    mode: PipelineMode = Field(default=PipelineMode.FULL, description="'full' (Stage 1-4) or 'partial' (targeted stages)")
    target_stages: Optional[List[StageType]] = Field(
        default=None,
        description="Explicit list of stages to run in 'partial' mode. In 'full' mode, all 4 stages are executed in order.",
    )
    stages: Optional[List[StageType]] = Field(
        default=None,
        description="Alias for target_stages",
    )
    feedback_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific feedback IDs to process. If omitted, unanalyzed/unassigned items are used.",
    )
    feature_group_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of existing feature group IDs (for partial prioritization or planning).",
    )
    selected_feature_group_id: Optional[str] = Field(
        default=None,
        description="Explicit feature group to plan in Product Planning stage. If omitted in full mode, top-ranked group is selected.",
    )
    strategic_context: Optional[ProductStrategicContext] = Field(
        default=None,
        description="Optional organizational strategic context for Product Planning and Prioritization.",
    )
    strategic_goals: Optional[List[str]] = Field(
        default=None,
        description="Optional strategic goals list alias for strategic_alignment_context.",
    )
    strategic_alignment_context: Optional[str] = Field(
        default=None,
        description="Optional strategic text guidance for prioritization scoring.",
    )
    usage_analytics_evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional verified usage analytics metrics. Null/missing indicates unmeasured usage (never zeroed).",
    )
    force_reanalyze: bool = Field(default=False, description="Re-run Feedback Intelligence even if analysis exists")
    force_regroup: bool = Field(default=False, description="Re-group feature requests even if groups already exist")
    force_recalculate_prioritization: bool = Field(default=False, description="Re-score prioritization scenarios")
    force_approved_overwrite: bool = Field(default=False, description="Explicit authorization to overwrite approved PRD")

    @model_validator(mode="before")
    @classmethod
    def handle_request_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "stages" in data and ("target_stages" not in data or not data["target_stages"]):
                data["target_stages"] = data["stages"]
            elif "target_stages" in data and ("stages" not in data or not data["stages"]):
                data["stages"] = data["target_stages"]
            if "strategic_goals" in data and ("strategic_alignment_context" not in data or not data["strategic_alignment_context"]):
                goals = data["strategic_goals"]
                if isinstance(goals, list):
                    data["strategic_alignment_context"] = "; ".join(str(g) for g in goals)
                elif isinstance(goals, str):
                    data["strategic_alignment_context"] = goals
        return data

    @model_validator(mode="after")
    def sync_target_stages(self) -> "OrchestratorRequest":
        if self.target_stages is None and self.stages is not None:
            self.target_stages = self.stages
        elif self.stages is None and self.target_stages is not None:
            self.stages = self.target_stages
        return self


class OrchestratorResponse(BaseModel):
    """Structured response representing the state and outputs of an orchestration run."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    run_id: str = Field(..., description="Unique orchestration run ID")
    workspace_id: str = Field(..., description="Target workspace ID")
    mode: PipelineMode = Field(..., description="Execution mode: full or partial")
    overall_status: PipelineStatus = Field(..., description="Overall pipeline status")
    status: Optional[PipelineStatus] = Field(default=None, description="Alias for overall_status")
    execution_summary: str = Field(default="", description="High-level narrative of pipeline outcome")
    stage_results: Dict[str, StageResult] = Field(default_factory=dict, description="Stage-by-stage results")
    stages: Optional[List[StageResult]] = Field(default=None, description="Alias for list of stage results")
    feedback_analysis_results: Optional[Any] = Field(
        default=None,
        description="Outputs from Stage 1 (Feedback Intelligence)",
    )
    generated_feature_groups: Optional[Any] = Field(
        default=None,
        description="Outputs from Stage 2 (Feature Intelligence)",
    )
    prioritization_results: Optional[Any] = Field(
        default=None,
        description="Outputs from Stage 3 (Prioritization)",
    )
    planning_result: Optional[Any] = Field(
        default=None,
        description="Output from Stage 4 (Product Planning)",
    )
    errors: List[str] = Field(default_factory=list, description="List of all operational errors encountered")
    warnings: List[str] = Field(default_factory=list, description="List of all advisory warnings")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Telemetry, model info, and token counts")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Pipeline execution start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Pipeline completion timestamp")
    total_execution_time_ms: float = Field(default=0.0, description="Total pipeline execution duration in milliseconds")
    total_duration_ms: Optional[float] = Field(default=None, description="Alias for total_execution_time_ms")

    def __init__(self, **data: Any):
        if "status" in data and "overall_status" not in data:
            data["overall_status"] = data["status"]
        if "stages" in data and "stage_results" not in data:
            stages_list = data["stages"]
            if isinstance(stages_list, list):
                data["stage_results"] = {
                    (s.stage.value if hasattr(s.stage, "value") else str(s.stage)): s
                    for s in stages_list
                }
            else:
                data["stage_results"] = stages_list
        if "total_duration_ms" in data and "total_execution_time_ms" not in data:
            data["total_execution_time_ms"] = data["total_duration_ms"]
        if "feedback_results" in data and "feedback_analysis_results" not in data:
            data["feedback_analysis_results"] = data.pop("feedback_results")
        if "feature_group_results" in data and "generated_feature_groups" not in data:
            data["generated_feature_groups"] = data.pop("feature_group_results")
        if "product_plan_result" in data and "planning_result" not in data:
            data["planning_result"] = data.pop("product_plan_result")
        super().__init__(**data)

    @model_validator(mode="after")
    def sync_aliases(self) -> "OrchestratorResponse":
        if self.status is None:
            self.status = self.overall_status
        if self.stages is None:
            self.stages = list(self.stage_results.values())
        if self.total_duration_ms is None:
            self.total_duration_ms = self.total_execution_time_ms
        return self

    @property
    def feedback_results(self) -> Optional[Any]:
        return self.feedback_analysis_results

    @property
    def feature_group_results(self) -> Optional[Any]:
        return self.generated_feature_groups

    @property
    def product_plan_result(self) -> Optional[Any]:
        return self.planning_result


class OrchestratorHealthResponse(BaseModel):
    """Health and specialist agent availability response."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    healthy: bool = Field(default=True, description="Boolean health status")
    provider: str = Field(default="groq", description="Configured LLM provider (e.g. groq)")
    model: str = Field(default="qwen/qwen3.8-27b", description="Configured LLM model")
    agents_available: Dict[str, bool] = Field(default_factory=dict, description="Availability status of each specialist agent")
    specialist_agents: List[Dict[str, Any]] = Field(default_factory=list, description="Specialist agents details")
    active_runs_cached: int = Field(default=0, description="Active cached runs")
    uptime_seconds: float = Field(default=0.0, description="Uptime in seconds")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
