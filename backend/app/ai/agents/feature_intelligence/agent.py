"""
ProductMind AI — Feature Intelligence Agent Implementation
Specialist agent converting dispersed customer feature requests into consolidated,
deduplicated, and semantically grouped feature intelligence.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Type, Union

from langchain_core.messages import HumanMessage
from app.ai.agents.base import BaseAgent, AgentExecutionMetadata, AgentExecutionResult
from app.ai.agents.feature_intelligence.prompts import (
    feature_grouping_prompt,
    duplicate_detection_prompt,
)
from app.ai.agents.feature_intelligence.schemas import (
    FeatureGroupingAgentOutput,
    FeatureRequestCandidate,
    DuplicateDetectionAgentOutput,
)
from app.ai.agents.feature_intelligence.grouping import (
    format_candidates_for_prompt,
)
from app.ai.exceptions import AIConfigurationException
from app.ai.llm_service import LLMService

logger = logging.getLogger("productmind.ai.agent.features")


class FeatureIntelligenceAgent(BaseAgent[FeatureGroupingAgentOutput]):
    """
    Feature Intelligence Agent for ProductMind AI.
    Analyzes eligible customer feature requests to detect duplicates, perform semantic
    clustering, extract grounded evidence and pain points, and synthesize consolidated
    feature specifications for product managers.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        super().__init__(llm_service=llm_service)

    @property
    def agent_id(self) -> str:
        return "feature_intelligence_agent"

    @property
    def agent_name(self) -> str:
        return "Feature Intelligence Agent"

    @property
    def agent_version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Clusters customer feature requests, detects duplicates, preserves original "
            "traceability, and generates consolidated feature intelligence for product planning."
        )

    @property
    def prompt_template(self):
        return feature_grouping_prompt

    @property
    def output_schema(self) -> Type[FeatureGroupingAgentOutput]:
        return FeatureGroupingAgentOutput

    def validate_input(self, input_data: Any) -> Dict[str, Any]:
        """
        Validates candidate feature requests and formats prompt parameters.
        Accepts a dict containing 'candidates' (List[FeatureRequestCandidate] or dicts),
        or raw text representation.
        """
        raw_dict = super().validate_input(input_data)

        candidates_raw = raw_dict.get("candidates")
        confidence_threshold = float(raw_dict.get("confidence_threshold", 0.6))
        min_group_size = int(raw_dict.get("min_group_size", 1))

        if candidates_raw is not None and isinstance(candidates_raw, list):
            if not candidates_raw:
                raise ValueError("candidates list cannot be empty for feature grouping")

            # Convert to FeatureRequestCandidate instances if needed
            candidate_objs: List[FeatureRequestCandidate] = []
            for c in candidates_raw:
                if isinstance(c, FeatureRequestCandidate):
                    candidate_objs.append(c)
                elif isinstance(c, dict):
                    candidate_objs.append(FeatureRequestCandidate(**c))
                elif hasattr(c, "model_dump"):
                    candidate_objs.append(FeatureRequestCandidate(**c.model_dump()))

            candidate_items_text = format_candidates_for_prompt(candidate_objs)
            candidate_count = len(candidate_objs)
        else:
            candidate_items_text = str(raw_dict.get("candidate_items_text") or "").strip()
            if not candidate_items_text:
                raise ValueError("Either 'candidates' list or 'candidate_items_text' must be provided")
            candidate_count = int(raw_dict.get("candidate_count", 1))

        return {
            "candidate_items_text": candidate_items_text,
            "candidate_count": candidate_count,
            "confidence_threshold": confidence_threshold,
            "min_group_size": min_group_size,
        }

    async def detect_duplicates(
        self,
        candidates: List[FeatureRequestCandidate],
        comparison_context: str = "",
        max_retries: int = 1,
        **kwargs: Any,
    ) -> AgentExecutionResult[DuplicateDetectionAgentOutput]:
        """
        Executes semantic duplicate detection across candidate requests using
        duplicate_detection_prompt and DuplicateDetectionAgentOutput structured schema.
        """
        if not self.llm_service.is_configured:
            raise AIConfigurationException(
                f"Active AI provider '{self.llm_service.provider_name}' is not configured.",
                provider=self.llm_service.provider_name,
            )

        items_text = format_candidates_for_prompt(candidates)
        context = comparison_context or "Evaluate all pairs of feedback items for mutual duplication vs distinctness."

        messages = duplicate_detection_prompt.format_messages(
            items_text=items_text,
            comparison_context=context,
        )

        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

        last_error: Optional[Exception] = None
        attempts = 0
        total_attempts = 1 + max(0, max_retries)

        while attempts < total_attempts:
            attempts += 1
            try:
                call_messages = list(messages)
                if attempts > 1 and last_error is not None:
                    call_messages.append(
                        HumanMessage(
                            content=f"Your previous response failed validation: {last_error}. Regenerate strictly according to the schema."
                        )
                    )

                result_data = await self.llm_service.provider.ainvoke_structured(
                    schema=DuplicateDetectionAgentOutput,
                    messages=call_messages,
                    **kwargs,
                )

                latency_ms = round((time.perf_counter() - start_perf) * 1000, 2)
                completed_at = datetime.now(timezone.utc)

                metadata = AgentExecutionMetadata(
                    agent_id=f"{self.agent_id}_duplicate_detector",
                    agent_name=f"{self.agent_name} (Duplicate Detector)",
                    agent_version=self.agent_version,
                    provider=self.llm_service.provider_name,
                    model=self.llm_service.model_name,
                    latency_ms=latency_ms,
                    started_at=started_at,
                    completed_at=completed_at,
                    attempts=attempts,
                )
                return AgentExecutionResult(data=result_data, metadata=metadata)

            except Exception as exc:
                last_error = exc
                logger.warning("Duplicate detection attempt %d failed: %s", attempts, exc)
                if attempts >= total_attempts:
                    raise

