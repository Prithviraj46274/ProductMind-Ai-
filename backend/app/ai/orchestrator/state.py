"""
ProductMind AI — Orchestration State Management & In-Memory Run Store
Manages lifecycle state, timestamps, stage progression, intermediate outputs,
and bounded run caching for retrieval.
"""

from collections import OrderedDict
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from app.ai.orchestrator.schemas import (
    OrchestratorResponse,
    PipelineMode,
    PipelineStatus,
    StageResult,
    StageStatus,
    StageType,
)


class PipelineExecutionState:
    """Manages the in-flight execution lifecycle and intermediate outputs of a pipeline run."""

    def __init__(
        self,
        workspace_id: str,
        mode: PipelineMode,
        stages_to_run: List[StageType],
        run_id: Optional[str] = None,
    ):
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:16]}"
        self.workspace_id = workspace_id
        self.mode = mode
        self.stages_to_run = stages_to_run
        self.overall_status = PipelineStatus.PENDING
        self.started_at = datetime.now(timezone.utc)
        self._start_perf = time.perf_counter()
        self.completed_at: Optional[datetime] = None

        # Initialize all canonical stages
        canonical_stages = [
            StageType.FEEDBACK_INTELLIGENCE,
            StageType.FEATURE_INTELLIGENCE,
            StageType.PRIORITIZATION,
            StageType.PRODUCT_PLANNING,
        ]
        self.stage_results: Dict[str, StageResult] = {
            st.value: StageResult(
                stage=st,
                status=StageStatus.PENDING if st in stages_to_run else StageStatus.SKIPPED,
                warning=None if st in stages_to_run else "Stage not selected in partial execution mode",
            )
            for st in canonical_stages
        }

        # Stage outputs
        self.feedback_results: Optional[Any] = None
        self.feature_group_results: Optional[Any] = None
        self.prioritization_results: Optional[Any] = None
        self.planning_result: Optional[Any] = None

        # Diagnostics
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.execution_metadata: Dict[str, Any] = {}
        self._stage_start_times: Dict[str, float] = {}

    def mark_stage_started(self, stage: StageType) -> None:
        self.overall_status = PipelineStatus.RUNNING
        self._stage_start_times[stage.value] = time.perf_counter()
        self.stage_results[stage.value] = StageResult(
            stage=stage,
            status=StageStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

    def mark_stage_completed(
        self,
        stage: StageType,
        metadata: Optional[Dict[str, Any]] = None,
        warning: Optional[str] = None,
    ) -> None:
        start_t = self._stage_start_times.get(stage.value, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
        prev = self.stage_results.get(stage.value)
        started_at = prev.started_at if prev else self.started_at

        self.stage_results[stage.value] = StageResult(
            stage=stage,
            status=StageStatus.COMPLETED,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            warning=warning,
            metadata=metadata or {},
        )
        if warning:
            self.warnings.append(f"[{stage.value}] {warning}")

    def mark_stage_failed(
        self,
        stage: StageType,
        error: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        start_t = self._stage_start_times.get(stage.value, time.perf_counter())
        duration_ms = round((time.perf_counter() - start_t) * 1000.0, 2)
        prev = self.stage_results.get(stage.value)
        started_at = prev.started_at if prev else self.started_at

        self.stage_results[stage.value] = StageResult(
            stage=stage,
            status=StageStatus.FAILED,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            error=error,
            metadata=metadata or {},
        )
        self.errors.append(f"[{stage.value}] {error}")

    def mark_stage_skipped(self, stage: StageType, reason: str) -> None:
        self.stage_results[stage.value] = StageResult(
            stage=stage,
            status=StageStatus.SKIPPED,
            warning=reason,
        )
        self.warnings.append(f"[{stage.value}] Skipped: {reason}")

    def finalize(self, summary_override: Optional[str] = None) -> OrchestratorResponse:
        self.completed_at = datetime.now(timezone.utc)
        total_time_ms = round((time.perf_counter() - self._start_perf) * 1000.0, 2)

        # Compute overall status
        statuses = [res.status for res in self.stage_results.values()]
        if any(s == StageStatus.FAILED for s in statuses):
            if any(s == StageStatus.COMPLETED for s in statuses):
                self.overall_status = PipelineStatus.PARTIALLY_COMPLETED
            else:
                self.overall_status = PipelineStatus.FAILED
        elif all(s in (StageStatus.COMPLETED, StageStatus.SKIPPED) for s in statuses):
            self.overall_status = PipelineStatus.COMPLETED
        else:
            self.overall_status = PipelineStatus.FAILED if self.errors else PipelineStatus.COMPLETED

        # Generate default summary if not provided
        if not summary_override:
            completed_count = sum(1 for s in statuses if s == StageStatus.COMPLETED)
            failed_count = sum(1 for s in statuses if s == StageStatus.FAILED)
            skipped_count = sum(1 for s in statuses if s == StageStatus.SKIPPED)
            summary = (
                f"Pipeline {self.overall_status.value}: {completed_count} completed, "
                f"{failed_count} failed, {skipped_count} skipped in {total_time_ms}ms"
            )
        else:
            summary = summary_override

        return OrchestratorResponse(
            run_id=self.run_id,
            workspace_id=self.workspace_id,
            mode=self.mode,
            overall_status=self.overall_status,
            execution_summary=summary,
            stage_results=self.stage_results,
            feedback_analysis_results=self.feedback_results,
            generated_feature_groups=self.feature_group_results,
            prioritization_results=self.prioritization_results,
            planning_result=self.planning_result,
            errors=self.errors,
            warnings=self.warnings,
            execution_metadata=self.execution_metadata,
            started_at=self.started_at,
            completed_at=self.completed_at,
            total_execution_time_ms=total_time_ms,
        )


class OrchestratorRunStore:
    """
    Thread-safe, bounded in-memory store for retrieving orchestration run histories
    without requiring unapproved database migrations.
    """

    def __init__(self, max_capacity: int = 500, capacity: Optional[int] = None):
        self._runs: OrderedDict[str, OrchestratorResponse] = OrderedDict()
        self._lock = threading.Lock()
        self._max_capacity = capacity if capacity is not None else max_capacity

    def save_run(self, run: OrchestratorResponse) -> None:
        with self._lock:
            if run.run_id in self._runs:
                del self._runs[run.run_id]
            elif len(self._runs) >= self._max_capacity:
                self._runs.popitem(last=False)  # Evict oldest run
            self._runs[run.run_id] = run

    def save(self, run: OrchestratorResponse) -> None:
        """Alias for save_run."""
        self.save_run(run)

    def get_run(self, run_id: str) -> Optional[OrchestratorResponse]:
        with self._lock:
            return self._runs.get(run_id)

    def get(self, run_id: str) -> Optional[OrchestratorResponse]:
        """Alias for get_run."""
        return self.get_run(run_id)

    def size(self) -> int:
        with self._lock:
            return len(self._runs)

    def list_runs(self, workspace_id: Optional[str] = None, limit: int = 20) -> List[OrchestratorResponse]:
        with self._lock:
            all_runs = list(self._runs.values())
            if workspace_id:
                all_runs = [r for r in all_runs if r.workspace_id == workspace_id]
            all_runs.reverse()  # Newest first
            return all_runs[:limit]

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


# Global default run store singleton
_default_run_store = OrchestratorRunStore()


def get_orchestrator_run_store() -> OrchestratorRunStore:
    return _default_run_store
