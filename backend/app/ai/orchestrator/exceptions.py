"""
ProductMind AI — AI Orchestrator Domain Exceptions
Defines standardized exception classes for pipeline coordination, stage dependencies,
validation, and partial execution failures.
"""

from typing import Optional
from app.ai.exceptions import AIServiceException


class OrchestratorException(AIServiceException):
    """Base exception for all AI Orchestrator operations."""

    def __init__(self, message: str, stage: Optional[str] = None, original_exception: Optional[Exception] = None):
        super().__init__(message=message, provider="orchestrator", original_exception=original_exception)
        self.stage = stage

    def __str__(self) -> str:
        stage_prefix = f"[{self.stage.upper()}] " if self.stage else ""
        return f"[ORCHESTRATOR] {stage_prefix}{self.message}"


class OrchestratorValidationException(OrchestratorException):
    """Raised when an orchestration request has invalid parameters or missing required data."""
    pass


class OrchestratorDependencyException(OrchestratorException):
    """Raised when stage prerequisites or dependencies are unsatisfied."""
    pass


class OrchestratorAuthorizationException(OrchestratorException):
    """Raised when user lacks permission to access workspace or requested resources."""
    pass


class OrchestratorStageExecutionException(OrchestratorException):
    """Raised when an individual specialist agent stage fails execution."""
    pass

