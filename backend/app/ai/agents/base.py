"""
ProductMind AI — Base Agent Execution Foundation
Defines the core contract, execution lifecycle, structured output validation,
retry mechanism, and telemetry tracking for all specialist product agents.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage
from app.ai.llm_service import LLMService, get_llm_service
from app.ai.prompts.base import BasePromptTemplate
from app.ai.exceptions import (
    AIServiceException,
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
    AISchemaValidationException,
)

logger = logging.getLogger("productmind.ai.agent.base")
T = TypeVar("T", bound=BaseModel)


class AgentExecutionMetadata(BaseModel):
    """Execution telemetry captured for every agent invocation."""
    agent_id: str
    agent_name: str
    agent_version: str
    provider: str
    model: str
    latency_ms: float
    started_at: datetime
    completed_at: datetime
    attempts: int = 1


class AgentExecutionResult(Generic[T]):
    """Standardized result envelope returned by all agent executions."""

    def __init__(self, data: T, metadata: AgentExecutionMetadata):
        self.data: T = data
        self.metadata: AgentExecutionMetadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data.model_dump(),
            "metadata": self.metadata.model_dump(),
        }

    def __repr__(self) -> str:
        return f"<AgentExecutionResult(agent='{self.metadata.agent_id}', status='success')>"


class BaseAgent(Generic[T], ABC):
    """
    Abstract Base Agent for ProductMind AI specialist agents.
    Encapsulates input validation, prompt rendering, structured LLM execution,
    controlled correction retry, and execution metadata capture.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service: LLMService = llm_service or get_llm_service()

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier (e.g., 'feedback_intelligence_agent')."""
        pass

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name (e.g., 'Feedback Intelligence Agent')."""
        pass

    @property
    @abstractmethod
    def agent_version(self) -> str:
        """Semantic version of the agent logic and prompts."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Summary of the agent's product management function."""
        pass

    @property
    @abstractmethod
    def prompt_template(self) -> BasePromptTemplate:
        """BasePromptTemplate instance defining system and user message formats."""
        pass

    @property
    @abstractmethod
    def output_schema(self) -> Type[T]:
        """Pydantic v2 schema target for structured output."""
        pass

    def validate_input(self, input_data: Any) -> Dict[str, Any]:
        """
        Validates and converts input payload into a dictionary for prompt variables.
        Subclasses should override to enforce domain-specific input constraints.
        """
        if isinstance(input_data, dict):
            return input_data
        if hasattr(input_data, "model_dump"):
            return input_data.model_dump()
        raise ValueError(f"Agent input must be a dictionary or Pydantic model, got {type(input_data).__name__}")

    async def execute(
        self,
        input_data: Any,
        max_retries: int = 1,
        **kwargs: Any,
    ) -> AgentExecutionResult[T]:
        """
        Executes the agent pipeline asynchronously:
        1. Validates input data.
        2. Formats prompt messages from template.
        3. Calls LLM with schema-enforced output.
        4. Retries once with correction context if output validation fails.
        5. Returns structured AgentExecutionResult with execution metadata.
        """
        # Validate that underlying provider is configured
        if not self.llm_service.is_configured:
            raise AIConfigurationException(
                f"Active AI provider '{self.llm_service.provider_name}' is not configured with required credentials.",
                provider=self.llm_service.provider_name,
            )

        variables = self.validate_input(input_data)
        messages = self.prompt_template.format_messages(**variables)

        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

        last_error: Optional[Exception] = None
        attempts = 0
        total_attempts = 1 + max(0, max_retries)

        while attempts < total_attempts:
            attempts += 1
            try:
                # If retrying after a validation error, append a corrective message
                call_messages = list(messages)
                if attempts > 1 and last_error is not None:
                    correction_prompt = (
                        f"Your previous response failed structured validation with error: {last_error}. "
                        "Please regenerate the response adhering strictly to the requested schema."
                    )
                    call_messages.append(HumanMessage(content=correction_prompt))

                structured_result = await self.llm_service.provider.ainvoke_structured(
                    schema=self.output_schema,
                    messages=call_messages,
                    **kwargs,
                )

                latency_ms = round((time.perf_counter() - start_perf) * 1000, 2)
                completed_at = datetime.now(timezone.utc)

                metadata = AgentExecutionMetadata(
                    agent_id=self.agent_id,
                    agent_name=self.agent_name,
                    agent_version=self.agent_version,
                    provider=self.llm_service.provider_name,
                    model=self.llm_service.model_name,
                    latency_ms=latency_ms,
                    started_at=started_at,
                    completed_at=completed_at,
                    attempts=attempts,
                )

                logger.info(
                    "Agent %s:v%s executed successfully via %s/%s (latency: %sms, attempts: %d)",
                    self.agent_id,
                    self.agent_version,
                    metadata.provider,
                    metadata.model,
                    metadata.latency_ms,
                    attempts,
                )

                return AgentExecutionResult(data=structured_result, metadata=metadata)

            except AISchemaValidationException as val_exc:
                last_error = val_exc
                logger.warning(
                    "Agent %s attempt %d/%d failed validation: %s",
                    self.agent_id,
                    attempts,
                    total_attempts,
                    val_exc,
                )
                if attempts >= total_attempts:
                    raise val_exc

            except (AIAuthenticationException, AIRateLimitException, AITimeoutException, AIProviderException):
                # Propagate operational domain errors directly without retrying
                raise

            except Exception as unhandled:
                logger.exception("Unexpected error executing agent %s: %s", self.agent_id, unhandled)
                raise AIServiceException(
                    f"Agent execution encountered an unexpected error: {type(unhandled).__name__}",
                    provider=self.llm_service.provider_name,
                    original_exception=unhandled,
                )

        # Fallback if loop exits without returning or raising
        raise AISchemaValidationException(
            f"Agent failed structured output after {attempts} attempts: {last_error}",
            provider=self.llm_service.provider_name,
            original_exception=last_error,
        )

