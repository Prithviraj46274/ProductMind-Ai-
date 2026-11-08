"""
ProductMind AI — Agent Foundation Unit Tests (Step 1.5)
Tests BasePromptTemplate, BaseAgent execution lifecycle, variable substitution,
structured output validation, error propagation, and controlled retry behavior.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel, Field

from app.ai.prompts.base import BasePromptTemplate
from app.ai.agents.base import (
    BaseAgent,
    AgentExecutionMetadata,
    AgentExecutionResult,
)
from app.ai.exceptions import (
    AIConfigurationException,
    AIAuthenticationException,
    AIRateLimitException,
    AITimeoutException,
    AIProviderException,
    AISchemaValidationException,
    AIServiceException,
)
from app.ai.llm_service import LLMService


# --- Sample Schemas & Dummy Agent for Testing ---

class SampleAgentOutput(BaseModel):
    summary: str
    confidence: float = Field(..., ge=0.0, le=1.0)


sample_prompt = BasePromptTemplate(
    name="test_agent_prompt",
    version="1.0.0",
    description="Test prompt for foundation verification",
    system_template="You are a product management copilot. Context: {system_context}",
    human_template="Analyze the following task: {user_input}",
    required_variables={"system_context", "user_input"},
)


class DummyAgent(BaseAgent[SampleAgentOutput]):
    @property
    def agent_id(self) -> str:
        return "dummy_test_agent"

    @property
    def agent_name(self) -> str:
        return "Dummy Test Agent"

    @property
    def agent_version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Agent used for unit testing foundation behaviors"

    @property
    def prompt_template(self) -> BasePromptTemplate:
        return sample_prompt

    @property
    def output_schema(self) -> type:
        return SampleAgentOutput


# --- Foundation Tests ---

def test_prompt_template_variable_substitution():
    """Verify prompt template successfully populates variables and outputs LangChain messages."""
    messages = sample_prompt.format_messages(
        system_context="Product Analytics",
        user_input="Evaluate retention metrics",
    )
    assert len(messages) == 2
    assert "Product Analytics" in messages[0].content
    assert "Evaluate retention metrics" in messages[1].content


def test_prompt_template_missing_variables_raises():
    """Verify prompt template raises ValueError if required variables are omitted."""
    with pytest.raises(ValueError) as exc_info:
        sample_prompt.format_messages(system_context="Only one provided")
    assert "missing required variables" in str(exc_info.value).lower()
    assert "user_input" in str(exc_info.value)


@pytest.mark.asyncio
async def test_base_agent_execution_success():
    """Verify successful agent execution captures execution metadata and structured data."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "groq"
    mock_service.model_name = "qwen/qwen3.8-27b"

    mock_provider = MagicMock()
    expected_output = SampleAgentOutput(summary="Analysis complete.", confidence=0.95)
    mock_provider.ainvoke_structured = AsyncMock(return_value=expected_output)
    mock_service.provider = mock_provider

    agent = DummyAgent(llm_service=mock_service)
    result = await agent.execute({
        "system_context": "Production",
        "user_input": "Test Input",
    })

    assert isinstance(result, AgentExecutionResult)
    assert result.data == expected_output
    assert result.data.summary == "Analysis complete."
    assert result.data.confidence == 0.95
    assert result.metadata.agent_id == "dummy_test_agent"
    assert result.metadata.provider == "groq"
    assert result.metadata.model == "qwen/qwen3.8-27b"
    assert result.metadata.latency_ms >= 0
    assert result.metadata.attempts == 1


@pytest.mark.asyncio
async def test_base_agent_unconfigured_raises():
    """Verify unconfigured provider raises AIConfigurationException."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.is_configured = False
    mock_service.provider_name = "groq"

    agent = DummyAgent(llm_service=mock_service)
    with pytest.raises(AIConfigurationException) as exc_info:
        await agent.execute({"system_context": "Ctx", "user_input": "Input"})
    assert "is not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_base_agent_schema_retry_success():
    """Verify base agent retries once with correction context if initial output fails validation."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "groq"
    mock_service.model_name = "qwen/qwen3.8-27b"

    mock_provider = MagicMock()
    valid_output = SampleAgentOutput(summary="Recovered on retry.", confidence=0.88)
    # Attempt 1 fails with validation error, attempt 2 succeeds
    mock_provider.ainvoke_structured = AsyncMock(
        side_effect=[
            AISchemaValidationException("Invalid JSON schema", provider="groq"),
            valid_output,
        ]
    )
    mock_service.provider = mock_provider

    agent = DummyAgent(llm_service=mock_service)
    result = await agent.execute(
        {"system_context": "Ctx", "user_input": "Input"},
        max_retries=1,
    )

    assert result.data == valid_output
    assert result.metadata.attempts == 2
    assert mock_provider.ainvoke_structured.await_count == 2


@pytest.mark.asyncio
async def test_base_agent_schema_exhaustion_raises():
    """Verify base agent raises AISchemaValidationException if retries are exhausted."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "groq"
    mock_service.model_name = "qwen/qwen3.8-27b"

    mock_provider = MagicMock()
    mock_provider.ainvoke_structured = AsyncMock(
        side_effect=AISchemaValidationException("Persistent invalid schema", provider="groq")
    )
    mock_service.provider = mock_provider

    agent = DummyAgent(llm_service=mock_service)
    with pytest.raises(AISchemaValidationException) as exc_info:
        await agent.execute(
            {"system_context": "Ctx", "user_input": "Input"},
            max_retries=1,
        )
    assert "Persistent invalid schema" in str(exc_info.value)
    assert mock_provider.ainvoke_structured.await_count == 2


@pytest.mark.asyncio
async def test_base_agent_propagates_operational_exceptions():
    """Verify rate-limit, timeout, auth, and provider errors are propagated immediately without retrying."""
    mock_service = MagicMock(spec=LLMService)
    mock_service.is_configured = True
    mock_service.provider_name = "groq"
    mock_service.model_name = "qwen/qwen3.8-27b"

    # 1. Rate Limit
    mock_provider = MagicMock()
    mock_provider.ainvoke_structured = AsyncMock(
        side_effect=AIRateLimitException("Quota exhausted", provider="groq")
    )
    mock_service.provider = mock_provider
    agent = DummyAgent(llm_service=mock_service)

    with pytest.raises(AIRateLimitException):
        await agent.execute({"system_context": "Ctx", "user_input": "Input"})
    assert mock_provider.ainvoke_structured.await_count == 1

    # 2. Timeout
    mock_provider.ainvoke_structured = AsyncMock(
        side_effect=AITimeoutException("Timeout exceeded", provider="groq")
    )
    with pytest.raises(AITimeoutException):
        await agent.execute({"system_context": "Ctx", "user_input": "Input"})
    assert mock_provider.ainvoke_structured.await_count == 1

    # 3. Authentication
    mock_provider.ainvoke_structured = AsyncMock(
        side_effect=AIAuthenticationException("Invalid key", provider="groq")
    )
    with pytest.raises(AIAuthenticationException):
        await agent.execute({"system_context": "Ctx", "user_input": "Input"})
    assert mock_provider.ainvoke_structured.await_count == 1

    # 4. Service Unavailable
    mock_provider.ainvoke_structured = AsyncMock(
        side_effect=AIProviderException("503 Unavailable", provider="groq")
    )
    with pytest.raises(AIProviderException):
        await agent.execute({"system_context": "Ctx", "user_input": "Input"})
    assert mock_provider.ainvoke_structured.await_count == 1

