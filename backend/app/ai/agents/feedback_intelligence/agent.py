"""
ProductMind AI — Feedback Intelligence Agent Implementation
Specialist agent converting unstructured feedback into structured product intelligence.
"""

import logging
from typing import Any, Dict, Optional, Type

from app.ai.agents.base import BaseAgent
from app.ai.agents.feedback_intelligence.prompts import feedback_intelligence_prompt
from app.ai.agents.feedback_intelligence.schemas import (
    FeedbackIntelligenceResult,
    AnalysisStatus,
    FeedbackClassificationCategory,
    FeedbackSentimentType,
    FeedbackUrgency,
)
from app.ai.llm_service import LLMService

logger = logging.getLogger("productmind.ai.agent.feedback")


class FeedbackIntelligenceAgent(BaseAgent[FeedbackIntelligenceResult]):
    """
    Feedback Intelligence Agent for ProductMind AI.
    Performs classification, sentiment extraction, calibrated urgency detection,
    thematic clustering, impact interpretation, and actionable next steps.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        super().__init__(llm_service=llm_service)

    @property
    def agent_id(self) -> str:
        return "feedback_intelligence_agent"

    @property
    def agent_name(self) -> str:
        return "Feedback Intelligence Agent"

    @property
    def agent_version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Analyzes customer feedback and support tickets to extract categories, "
            "sentiment, urgency, grounded pain points, and product impacts."
        )

    @property
    def prompt_template(self):
        return feedback_intelligence_prompt

    @property
    def output_schema(self) -> Type[FeedbackIntelligenceResult]:
        return FeedbackIntelligenceResult

    def validate_input(self, input_data: Any) -> Dict[str, Any]:
        """Validates feedback item fields and builds normalized prompt parameters."""
        raw_dict = super().validate_input(input_data)

        feedback_id = str(raw_dict.get("feedback_id") or raw_dict.get("_id") or raw_dict.get("id") or "").strip()
        if not feedback_id:
            raise ValueError("feedback_id is required for feedback intelligence analysis")

        title = str(raw_dict.get("title") or "").strip()
        description = str(raw_dict.get("description") or "").strip()
        if not title and not description:
            raise ValueError("Feedback item must contain a non-empty title or description")

        source_type = str(raw_dict.get("source_type") or raw_dict.get("sourceType") or "manual")

        customer_name = raw_dict.get("customer_name") or raw_dict.get("customerName") or ""
        company_name = raw_dict.get("company_name") or raw_dict.get("companyName") or ""

        context_parts = []
        if customer_name:
            context_parts.append(f"Customer: {customer_name}")
        if company_name:
            context_parts.append(f"Company: {company_name}")
        customer_context = ", ".join(context_parts) if context_parts else "Anonymous / General user"

        return {
            "feedback_id": feedback_id,
            "title": title or "Untitled Feedback",
            "description": description or "(No detailed description provided)",
            "source_type": source_type,
            "customer_context": customer_context,
        }

