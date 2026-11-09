"""
ProductMind AI — Product Planning Agent Implementation
Specialist agent transforming prioritized feature groups and customer feedback into
evidence-grounded PRDs, user stories, acceptance criteria, technical requirements,
success metrics, risk analysis, and roadmap recommendations.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Type

from app.ai.agents.base import BaseAgent, AgentExecutionResult
from app.ai.agents.product_planning.prompts import (
    product_planning_prompt,
    prd_generation_prompt,
    user_stories_prompt,
)
from app.ai.agents.product_planning.schemas import (
    ProductPlanningAgentOutput,
    ProductRequirementsDocument,
    PRDAgentOutput,
    UserStoriesAgentOutput,
    ProductStrategicContext,
    UserStory,
)
from app.ai.llm_service import LLMService

logger = logging.getLogger("productmind.ai.agent.product_planning")


def format_product_planning_prompt_inputs(
    group_id: str,
    title: str,
    description: str,
    feedback_count: int,
    unique_customer_count: int,
    pain_points: List[str],
    evidence: List[str],
    themes: List[str],
    urgency_dist: Optional[Dict[str, int]] = None,
    sentiment_dist: Optional[Dict[str, int]] = None,
    prioritization_data: Optional[Dict[str, Any]] = None,
    strategic_context: Optional[ProductStrategicContext] = None,
) -> Dict[str, str]:
    """
    Formats domain data into clear, evidence-grounded prompt sections.
    """
    # 1. Feature Group & Customer Evidence
    pain_points_bullet = (
        "\n".join(f"  - [PAIN POINT] {p}" for p in pain_points) if pain_points else "  - None explicitly recorded"
    )
    themes_bullet = (
        "\n".join(f"  - {t}" for t in themes) if themes else "  - None specified"
    )
    evidence_bullet = (
        "\n".join(f"  - [CUSTOMER QUOTE] \"{e}\"" for e in evidence[:10]) if evidence else "  - No direct quotes recorded"
    )
    urgency_str = (
        ", ".join(f"{k}: {v}" for k, v in urgency_dist.items()) if urgency_dist else "Not classified"
    )
    sentiment_str = (
        ", ".join(f"{k}: {v}" for k, v in sentiment_dist.items()) if sentiment_dist else "Not classified"
    )

    feature_group_text = (
        f"Feature Group ID: {group_id}\n"
        f"Feature Title: {title}\n"
        f"Description: {description or 'No detailed description provided'}\n"
        f"Customer Demand Volume: {feedback_count} requests from {unique_customer_count} distinct accounts\n"
        f"Urgency Breakdown: {urgency_str}\n"
        f"Sentiment Friction: {sentiment_str}\n"
        f"Verified Customer Pain Points (SOURCE-SUPPORTED):\n{pain_points_bullet}\n"
        f"Key Extracted Themes:\n{themes_bullet}\n"
        f"Direct Customer Quotes & Evidence (SOURCE-SUPPORTED):\n{evidence_bullet}"
    )

    # 2. Prioritization & Impact Intelligence
    if prioritization_data:
        p_score = prioritization_data.get("final_score")
        p_level = prioritization_data.get("priority_level", "Unclassified")
        f_scores = prioritization_data.get("factor_scores", {})
        f_scores_str = ", ".join(f"{k}: {v:.1f}" for k, v in f_scores.items()) if f_scores else "None"
        explanation = prioritization_data.get("explanation", "None provided")
        benefits = prioritization_data.get("implementation_benefits", [])
        benefits_bullet = "\n".join(f"  - {b}" for b in benefits) if benefits else "  - None recorded"
        risks = prioritization_data.get("delay_risks", [])
        risks_bullet = "\n".join(f"  - {r}" for r in risks) if risks else "  - None recorded"
        missing = prioritization_data.get("missing_data", [])
        missing_str = ", ".join(missing) if missing else "None"

        prioritization_text = (
            f"Prioritization Status: Evaluated\n"
            f"Composite Priority Score: {p_score} / 100 ({p_level} Priority)\n"
            f"Factor Breakdown: {f_scores_str}\n"
            f"Prioritization Rationale: {explanation}\n"
            f"Anticipated Implementation Benefits:\n{benefits_bullet}\n"
            f"Documented Delay Risks:\n{risks_bullet}\n"
            f"Excluded / Missing Analytics Factors: {missing_str}"
        )
    else:
        prioritization_text = (
            "Prioritization Status: Not separately evaluated before planning.\n"
            "Note: Generate planning recommendations based strictly on customer request volume, "
            "pain points, and stated customer needs. Do not invent prior composite scores."
        )

    # 3. Organizational Strategic Context
    if strategic_context and (
        strategic_context.product_name
        or strategic_context.business_goals
        or strategic_context.current_quarter_objectives
        or strategic_context.technical_constraints
        or strategic_context.known_dependencies
        or strategic_context.additional_planning_instructions
    ):
        lines = []
        if strategic_context.product_name:
            lines.append(f"Product: {strategic_context.product_name}")
        if strategic_context.product_description:
            lines.append(f"Product Context: {strategic_context.product_description}")
        if strategic_context.target_customer_segments:
            lines.append("Target Segments: " + ", ".join(strategic_context.target_customer_segments))
        if strategic_context.business_goals:
            lines.append("Strategic Goals:\n" + "\n".join(f"  - {g}" for g in strategic_context.business_goals))
        if strategic_context.current_quarter_objectives:
            lines.append("Quarterly OKRs:\n" + "\n".join(f"  - {o}" for o in strategic_context.current_quarter_objectives))
        if strategic_context.technical_constraints:
            lines.append("Mandatory Technical Constraints (USER-PROVIDED):\n" + "\n".join(f"  - {c}" for c in strategic_context.technical_constraints))
        if strategic_context.known_dependencies:
            lines.append("Known System Dependencies (USER-PROVIDED):\n" + "\n".join(f"  - {d}" for d in strategic_context.known_dependencies))
        if strategic_context.additional_planning_instructions:
            lines.append(f"Custom PM Directives (USER-PROVIDED): {strategic_context.additional_planning_instructions}")

        strategic_context_text = "\n".join(lines)
    else:
        strategic_context_text = (
            "No custom enterprise strategic context provided. Apply standard B2B SaaS product best practices:\n"
            "- Target role: Primary platform end-users and administrators.\n"
            "- Core goals: Streamline user workflow, eliminate friction, preserve system reliability, and reduce churn.\n"
            "- Technical baseline: Standard modern REST/JSON microservices architecture."
        )

    return {
        "feature_group_text": feature_group_text,
        "prioritization_text": prioritization_text,
        "strategic_context_text": strategic_context_text,
    }


class ProductPlanningAgent(BaseAgent[ProductPlanningAgentOutput]):
    """
    Product Planning Agent for ProductMind AI.
    Generates structured, traceable Product Requirements Documents, User Stories with
    Given-When-Then Acceptance Criteria, Technical Suggestions, Success Metrics, and Roadmaps.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        super().__init__(llm_service=llm_service)

    @property
    def agent_id(self) -> str:
        return "product_planning_agent"

    @property
    def agent_name(self) -> str:
        return "Product Planning Agent"

    @property
    def agent_version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return (
            "Transforms prioritized feature requests into structured, evidence-grounded PRDs, "
            "Agile user stories, acceptance criteria, technical recommendations, and delivery roadmaps."
        )

    @property
    def prompt_template(self):
        return product_planning_prompt

    @property
    def output_schema(self) -> Type[ProductPlanningAgentOutput]:
        return ProductPlanningAgentOutput

    # Alias for async consistency
    aexecute = BaseAgent.execute

    def validate_input(self, input_data: Any) -> Dict[str, Any]:
        """Validates that all required prompt fields are provided."""
        raw_dict = super().validate_input(input_data)

        fg_text = str(raw_dict.get("feature_group_text") or "").strip()
        if not fg_text:
            raise ValueError("feature_group_text cannot be empty for product planning")

        p_text = str(raw_dict.get("prioritization_text") or "").strip()
        if not p_text:
            p_text = "Prioritization Status: Not separately evaluated before planning."

        sc_text = str(raw_dict.get("strategic_context_text") or "").strip()
        if not sc_text:
            sc_text = "Standard SaaS product planning context: user productivity, reliability, retention."

        return {
            "feature_group_text": fg_text,
            "prioritization_text": p_text,
            "strategic_context_text": sc_text,
        }

    async def agenerate_plan(
        self,
        group_id: str,
        title: str,
        description: str,
        feedback_count: int,
        unique_customer_count: int,
        pain_points: List[str],
        evidence: List[str],
        themes: List[str],
        urgency_dist: Optional[Dict[str, int]] = None,
        sentiment_dist: Optional[Dict[str, int]] = None,
        prioritization_data: Optional[Dict[str, Any]] = None,
        strategic_context: Optional[ProductStrategicContext] = None,
        max_retries: int = 1,
        max_output_tokens: int = 1500,
    ) -> AgentExecutionResult[ProductPlanningAgentOutput]:
        """
        Executes complete product planning workflow:
        PRD, user stories, acceptance criteria, technical recommendations, metrics, and roadmap.
        Uses temperature=0.1 for maximum determinism and caps output tokens within Groq tier limits.
        """
        inputs = format_product_planning_prompt_inputs(
            group_id=group_id,
            title=title,
            description=description,
            feedback_count=feedback_count,
            unique_customer_count=unique_customer_count,
            pain_points=pain_points,
            evidence=evidence,
            themes=themes,
            urgency_dist=urgency_dist,
            sentiment_dist=sentiment_dist,
            prioritization_data=prioritization_data,
            strategic_context=strategic_context,
        )

        validated = self.validate_input(inputs)
        result = await self.execute(
            validated,
            max_retries=max_retries,
            temperature=0.1,
            max_output_tokens=max_output_tokens,
        )

        # Enforce feature_group_id alignment
        if not result.data.feature_group_id or result.data.feature_group_id != group_id:
            result.data.feature_group_id = group_id

        return result

    async def agenerate_prd(
        self,
        group_id: str,
        title: str,
        description: str,
        feedback_count: int,
        unique_customer_count: int,
        pain_points: List[str],
        evidence: List[str],
        themes: List[str],
        urgency_dist: Optional[Dict[str, int]] = None,
        sentiment_dist: Optional[Dict[str, int]] = None,
        prioritization_data: Optional[Dict[str, Any]] = None,
        strategic_context: Optional[ProductStrategicContext] = None,
        max_retries: int = 1,
        max_output_tokens: int = 800,
    ) -> ProductRequirementsDocument:
        """
        Generates or regenerates specifically the PRD portion.
        """
        inputs = format_product_planning_prompt_inputs(
            group_id=group_id,
            title=title,
            description=description,
            feedback_count=feedback_count,
            unique_customer_count=unique_customer_count,
            pain_points=pain_points,
            evidence=evidence,
            themes=themes,
            urgency_dist=urgency_dist,
            sentiment_dist=sentiment_dist,
            prioritization_data=prioritization_data,
            strategic_context=strategic_context,
        )

        messages = prd_generation_prompt.format_messages(**inputs)
        result = await self.llm_service.provider.ainvoke_structured(
            schema=PRDAgentOutput,
            messages=messages,
            temperature=0.1,
            max_output_tokens=max_output_tokens,
        )
        return result.prd

    async def agenerate_user_stories(
        self,
        group_id: str,
        title: str,
        description: str,
        feedback_count: int,
        unique_customer_count: int,
        pain_points: List[str],
        evidence: List[str],
        themes: List[str],
        urgency_dist: Optional[Dict[str, int]] = None,
        sentiment_dist: Optional[Dict[str, int]] = None,
        prioritization_data: Optional[Dict[str, Any]] = None,
        strategic_context: Optional[ProductStrategicContext] = None,
        max_retries: int = 1,
        max_output_tokens: int = 800,
    ) -> List[UserStory]:
        """
        Generates or regenerates specifically the user stories and acceptance criteria.
        """
        inputs = format_product_planning_prompt_inputs(
            group_id=group_id,
            title=title,
            description=description,
            feedback_count=feedback_count,
            unique_customer_count=unique_customer_count,
            pain_points=pain_points,
            evidence=evidence,
            themes=themes,
            urgency_dist=urgency_dist,
            sentiment_dist=sentiment_dist,
            prioritization_data=prioritization_data,
            strategic_context=strategic_context,
        )

        messages = user_stories_prompt.format_messages(**inputs)
        result = await self.llm_service.provider.ainvoke_structured(
            schema=UserStoriesAgentOutput,
            messages=messages,
            temperature=0.1,
            max_output_tokens=max_output_tokens,
        )
        return result.user_stories
