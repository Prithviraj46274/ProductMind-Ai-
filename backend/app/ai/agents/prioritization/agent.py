"""
ProductMind AI — Prioritization Agent Implementation
Specialist agent evaluating feature groups to generate explainable, evidence-based
qualitative prioritization intelligence, business impact, and strategic alignment.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Type

from app.ai.agents.base import BaseAgent, AgentExecutionResult
from app.ai.agents.prioritization.prompts import prioritization_prompt
from app.ai.agents.prioritization.schemas import (
    PrioritizationAgentOutput,
    StrategicContext,
    ProductAnalyticsData,
)
from app.ai.llm_service import LLMService

logger = logging.getLogger("productmind.ai.agent.prioritization")


def format_prioritization_prompt_inputs(
    group_id: str,
    title: str,
    description: str,
    pain_points: List[str],
    evidence: List[str],
    feedback_count: int,
    unique_customer_count: int,
    urgency_dist: Dict[str, int],
    sentiment_dist: Dict[str, int],
    strategic_context: Optional[StrategicContext] = None,
    analytics_data: Optional[ProductAnalyticsData] = None,
) -> Dict[str, str]:
    """
    Formats structured domain models into clear, structured prompt text sections.
    """
    # 1. Feature Group Text
    pain_points_bullet = "\n".join(f"  - {p}" for p in pain_points) if pain_points else "  - None specified"
    evidence_bullet = "\n".join(f"  - \"{e}\"" for e in evidence[:10]) if evidence else "  - No direct quotes recorded"

    feature_group_text = (
        f"Feature Group ID: {group_id}\n"
        f"Title: {title}\n"
        f"Description: {description or 'No detailed description'}\n"
        f"Identified Customer Pain Points:\n{pain_points_bullet}\n"
        f"Direct Customer Quotes & Evidence:\n{evidence_bullet}"
    )

    # 2. Demand & Sentiment Metrics
    urgency_str = ", ".join(f"{k}: {v}" for k, v in urgency_dist.items()) if urgency_dist else "Not classified"
    sentiment_str = ", ".join(f"{k}: {v}" for k, v in sentiment_dist.items()) if sentiment_dist else "Not classified"

    demand_metrics_text = (
        f"Total Customer Requests: {feedback_count}\n"
        f"Distinct Customer Accounts: {unique_customer_count}\n"
        f"Urgency Distribution: {urgency_str}\n"
        f"Sentiment Friction Distribution: {sentiment_str}"
    )

    # 3. Strategic Context
    if strategic_context and (
        strategic_context.primary_business_goals
        or strategic_context.current_quarter_okrs
        or strategic_context.company_stage
    ):
        stage_str = f"Company Stage: {strategic_context.company_stage}\n" if strategic_context.company_stage else ""
        goals_str = (
            "Primary Business Goals:\n" + "\n".join(f"  - {g}" for g in strategic_context.primary_business_goals)
            if strategic_context.primary_business_goals
            else ""
        )
        okrs_str = (
            "Current Quarter OKRs:\n" + "\n".join(f"  - {o}" for o in strategic_context.current_quarter_okrs)
            if strategic_context.current_quarter_okrs
            else ""
        )
        segments_str = (
            "Target Segments: " + ", ".join(strategic_context.target_customer_segments)
            if strategic_context.target_customer_segments
            else ""
        )
        strategic_context_text = "\n".join(filter(None, [stage_str, goals_str, okrs_str, segments_str]))
    else:
        strategic_context_text = (
            "No explicit corporate OKRs specified. Evaluate alignment against standard B2B SaaS "
            "product health: user productivity, operational stability, platform retention, and core capability value."
        )

    # 4. Product Analytics Summary
    if analytics_data and analytics_data.is_available:
        analytics_lines = ["Verified Product Analytics Available:"]
        if analytics_data.active_users is not None:
            analytics_lines.append(f"  - Active Users: {analytics_data.active_users}")
        if analytics_data.adoption_rate is not None:
            analytics_lines.append(f"  - Adoption Rate: {analytics_data.adoption_rate}%")
        if analytics_data.drop_off_rate is not None:
            analytics_lines.append(f"  - Funnel Drop-off Rate: {analytics_data.drop_off_rate}%")
        if analytics_data.user_engagement_score is not None:
            analytics_lines.append(f"  - User Engagement Score: {analytics_data.user_engagement_score}/100")
        if analytics_data.trend_direction:
            analytics_lines.append(f"  - Usage Trend: {analytics_data.trend_direction}")
        analytics_summary_text = "\n".join(analytics_lines)
    else:
        analytics_summary_text = (
            "No verified product usage analytics available for this feature. "
            "Usage impact factor will be omitted from score calculations and its weight reweighted."
        )

    return {
        "feature_group_text": feature_group_text,
        "demand_metrics_text": demand_metrics_text,
        "strategic_context_text": strategic_context_text,
        "analytics_summary_text": analytics_summary_text,
    }


class PrioritizationAgent(BaseAgent[PrioritizationAgentOutput]):
    """
    Prioritization Agent for ProductMind AI.
    Analyzes customer feature groups against business goals, customer evidence, and
    sentiment metrics to generate qualitative assessments of Business Impact and Strategic Alignment.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        super().__init__(llm_service=llm_service)

    @property
    def agent_id(self) -> str:
        return "prioritization_agent"

    @property
    def agent_name(self) -> str:
        return "Prioritization Agent"

    @property
    def agent_version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Evaluates feature groups to generate explainable qualitative prioritization intelligence, "
            "business impact scores, strategic alignment scores, implementation benefits, and delay risks."
        )

    @property
    def prompt_template(self):
        return prioritization_prompt

    @property
    def output_schema(self) -> Type[PrioritizationAgentOutput]:
        return PrioritizationAgentOutput

    # Alias for backward-compatibility with async naming conventions
    aexecute = BaseAgent.execute

    def validate_input(self, input_data: Any) -> Dict[str, Any]:
        """
        Validates prompt parameters for the Prioritization Agent.
        Accepts dictionary containing prompt variables.
        """
        raw_dict = super().validate_input(input_data)

        feature_group_text = str(raw_dict.get("feature_group_text") or "").strip()
        if not feature_group_text:
            raise ValueError("feature_group_text cannot be empty for prioritization evaluation")

        demand_metrics_text = str(raw_dict.get("demand_metrics_text") or "").strip()
        if not demand_metrics_text:
            raise ValueError("demand_metrics_text cannot be empty for prioritization evaluation")

        strategic_context_text = str(
            raw_dict.get("strategic_context_text")
            or "No explicit corporate OKRs specified. Prioritize core productivity and platform retention."
        ).strip()

        analytics_summary_text = str(
            raw_dict.get("analytics_summary_text")
            or "No verified product usage analytics available. Usage impact will be reweighted."
        ).strip()

        return {
            "feature_group_text": feature_group_text,
            "demand_metrics_text": demand_metrics_text,
            "strategic_context_text": strategic_context_text,
            "analytics_summary_text": analytics_summary_text,
        }

    async def aevaluate(
        self,
        group_id: str,
        title: str,
        description: str,
        pain_points: List[str],
        evidence: List[str],
        feedback_count: int,
        unique_customer_count: int,
        urgency_dist: Dict[str, int],
        sentiment_dist: Dict[str, int],
        strategic_context: Optional[StrategicContext] = None,
        analytics_data: Optional[ProductAnalyticsData] = None,
        max_retries: int = 1,
        max_output_tokens: int = 800,
    ) -> AgentExecutionResult[PrioritizationAgentOutput]:
        """
        Convenience method that formats domain inputs and executes the agent asynchronously.
        Uses temperature=0.1 for high determinism and stability.
        """
        prompt_inputs = format_prioritization_prompt_inputs(
            group_id=group_id,
            title=title,
            description=description,
            pain_points=pain_points,
            evidence=evidence,
            feedback_count=feedback_count,
            unique_customer_count=unique_customer_count,
            urgency_dist=urgency_dist,
            sentiment_dist=sentiment_dist,
            strategic_context=strategic_context,
            analytics_data=analytics_data,
        )

        validated = self.validate_input(prompt_inputs)
        result = await self.execute(
            validated,
            max_retries=max_retries,
            temperature=0.1,
            max_output_tokens=max_output_tokens,
        )

        # Enforce that the output contains the correct feature_group_id
        if not result.data.feature_group_id or result.data.feature_group_id != group_id:
            result.data.feature_group_id = group_id

        return result
