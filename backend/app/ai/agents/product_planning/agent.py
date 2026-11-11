"""
ProductMind AI — Product Planning Agent Implementation
Specialist agent transforming prioritized feature groups and customer feedback into
evidence-grounded PRDs, user stories, acceptance criteria, technical requirements,
success metrics, risk analysis, and roadmap recommendations.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_core.messages import BaseMessage, HumanMessage

from app.ai.agents.base import BaseAgent, AgentExecutionMetadata, AgentExecutionResult
from app.ai.agents.product_planning.prompts import (
    product_planning_prompt,
    prd_generation_prompt,
    prd_narrative_prompt,
    prd_requirements_prompt,
    user_stories_prompt,
    technical_specs_prompt,
)
from app.ai.agents.product_planning.schemas import (
    ProductPlanningAgentOutput,
    ProductRequirementsDocument,
    PRDAgentOutput,
    CorePRDNarrativeOutput,
    CorePRDRequirementsOutput,
    UserStoriesAgentOutput,
    TechnicalSpecsAgentOutput,
    ProductStrategicContext,
    UserStory,
)
from app.ai.exceptions import (
    AIConfigurationException,
    AIProviderException,
    AISchemaValidationException,
    AIServiceException,
)
from app.ai.llm_service import LLMService

logger = logging.getLogger("productmind.ai.agent.product_planning")
StageModelT = TypeVar("StageModelT", bound=BaseModel)


def _merge_evidence_quotes(*collections: Optional[List[str]]) -> List[str]:
    """Combines and deduplicates non-empty verbatim evidence quotes preserving order."""
    seen = set()
    merged: List[str] = []
    for coll in collections:
        if not coll:
            continue
        for item in coll:
            cleaned = str(item or "").strip()
            if not cleaned or cleaned.lower() in {"n/a", "na", "none", "null", "unknown"}:
                continue
            if cleaned not in seen:
                seen.add(cleaned)
                merged.append(cleaned)
    return merged


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

    async def _ainvoke_stage_structured(
        self,
        stage_name: str,
        schema: Type[StageModelT],
        messages: List[BaseMessage],
        max_retries: int = 1,
        max_output_tokens: int = 950,
    ) -> Tuple[StageModelT, int]:
        """
        Executes a single planning stage against `self.llm_service` with structured
        validation, controlled corrective retry on schema/parser failures, and
        explicit error context so partial failures never save incomplete PRDs.
        """
        if not self.llm_service.is_configured:
            raise AIConfigurationException(
                f"Active AI provider '{self.llm_service.provider_name}' is not configured with required credentials.",
                provider=self.llm_service.provider_name,
            )

        last_error: Optional[Exception] = None
        attempts = 0
        total_attempts = 1 + max(0, max_retries)

        while attempts < total_attempts:
            attempts += 1
            call_messages = list(messages)
            if attempts > 1 and last_error is not None:
                call_messages.append(
                    HumanMessage(
                        content=(
                            f"Previous {stage_name} generation failed structured validation ({last_error}). "
                            "Keep every field concise and return strictly valid JSON matching the requested schema."
                        )
                    )
                )
            try:
                result = await self.llm_service.provider.ainvoke_structured(
                    schema=schema,
                    messages=call_messages,
                    temperature=0.1,
                    max_output_tokens=max_output_tokens,
                )
                return result, attempts
            except (AISchemaValidationException, ValidationError) as exc:
                last_error = exc
                logger.warning(
                    "Product planning stage '%s' validation error on attempt %d/%d: %s",
                    stage_name,
                    attempts,
                    total_attempts,
                    exc,
                )
                if attempts >= total_attempts:
                    raise AISchemaValidationException(
                        f"Product planning stage '{stage_name}' failed structured validation: {exc}",
                        provider=self.llm_service.provider_name,
                        original_exception=exc,
                    )
            except AIProviderException as exc:
                last_error = exc
                orig_name = type(getattr(exc, "original_exception", None)).__name__.lower()
                is_parse_failure = "outputparser" in orig_name or "json" in str(exc).lower()
                if is_parse_failure and attempts < total_attempts:
                    logger.warning(
                        "Product planning stage '%s' encountered parser error (%s); retrying (%d/%d).",
                        stage_name,
                        exc,
                        attempts,
                        total_attempts,
                    )
                    continue
                raise AIProviderException(
                    f"Product planning stage '{stage_name}' failed: {exc}",
                    provider=self.llm_service.provider_name,
                    original_exception=getattr(exc, "original_exception", exc),
                )
            except AIServiceException:
                raise
            except Exception as exc:
                last_error = exc
                if attempts >= total_attempts:
                    raise AIServiceException(
                        f"Product planning stage '{stage_name}' failed unexpectedly: {exc}",
                        provider=self.llm_service.provider_name,
                        original_exception=exc,
                    )

        raise AISchemaValidationException(
            f"Product planning stage '{stage_name}' exhausted {total_attempts} attempts: {last_error}",
            provider=self.llm_service.provider_name,
            original_exception=last_error,
        )

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
        max_output_tokens: int = 950,
    ) -> AgentExecutionResult[ProductPlanningAgentOutput]:
        """
        Executes staged product planning workflow using the existing ProductPlanningAgent
        and LLMService:
        Stage 1: Core PRD sections (PRDAgentOutput)
        Stage 2: User stories and Given-When-Then acceptance criteria (UserStoriesAgentOutput)
        Stage 3: Technical requirements, metrics, risks, and roadmap (TechnicalSpecsAgentOutput)
        Stage 4: Combine sections and preserve customer evidence references
        Stage 5: Validate final document strictly against ProductPlanningAgentOutput
        """
        started_at = datetime.now(timezone.utc)
        start_perf = time.perf_counter()

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
        validated_inputs = self.validate_input(inputs)
        stage_budget = min(max(int(max_output_tokens or 950), 700), 950)
        total_attempts = 0

        # Stage 1a & 1b: Core PRD sections split cleanly to stay strictly under Groq OTPM limits
        narrative_messages = prd_narrative_prompt.format_messages(**validated_inputs)
        stage1a_out, attempts1a = await self._ainvoke_stage_structured(
            stage_name="core_prd_narrative",
            schema=CorePRDNarrativeOutput,
            messages=narrative_messages,
            max_retries=max_retries,
            max_output_tokens=stage_budget,
        )
        total_attempts += attempts1a

        # Support legacy full-PRD mock responses cleanly while always splitting real CorePRDNarrativeOutput
        if getattr(stage1a_out, "prd", None) is not None:
            prd_doc = stage1a_out.prd
        else:
            req_messages = prd_requirements_prompt.format_messages(**validated_inputs)
            stage1b_out, attempts1b = await self._ainvoke_stage_structured(
                stage_name="core_prd_requirements",
                schema=CorePRDRequirementsOutput,
                messages=req_messages,
                max_retries=max_retries,
                max_output_tokens=stage_budget,
            )
            total_attempts += attempts1b

            prd_doc = ProductRequirementsDocument.model_validate(
                {
                    "title": getattr(stage1a_out, "title", ""),
                    "executive_summary": getattr(stage1a_out, "executive_summary", ""),
                    "problem_statement": getattr(stage1a_out, "problem_statement", ""),
                    "background": getattr(stage1a_out, "background", ""),
                    "proposed_solution": getattr(stage1a_out, "proposed_solution", ""),
                    "customer_pain_points": getattr(stage1a_out, "customer_pain_points", []),
                    "target_users": getattr(stage1a_out, "target_users", []),
                    "business_objectives": getattr(stage1a_out, "business_objectives", []),
                    "workflows": getattr(stage1a_out, "workflows", []),
                    "out_of_scope": getattr(stage1a_out, "out_of_scope", []),
                    "open_questions": getattr(stage1a_out, "open_questions", []),
                    "supporting_evidence": _merge_evidence_quotes(
                        getattr(stage1a_out, "supporting_evidence", []),
                        evidence,
                    ),
                    "functional_requirements": [
                        r.model_dump() for r in (getattr(stage1b_out, "functional_requirements", []) or [])
                    ],
                    "non_functional_requirements": [
                        r.model_dump() for r in (getattr(stage1b_out, "non_functional_requirements", []) or [])
                    ],
                    "dependencies": getattr(stage1b_out, "dependencies", []) or [],
                    "risks_and_assumptions": getattr(stage1b_out, "risks_and_assumptions", []) or [],
                    "success_metrics": getattr(stage1b_out, "success_metrics", []) or [],
                }
            )

        if (
            not prd_doc
            or not (prd_doc.title or "").strip()
            or not (prd_doc.executive_summary or "").strip()
            or not (prd_doc.problem_statement or "").strip()
            or not (prd_doc.proposed_solution or "").strip()
        ):
            raise AISchemaValidationException(
                "Product planning stage 'core_prd' produced an incomplete PRD document.",
                provider=self.llm_service.provider_name,
            )

        # Stage 2: User stories and acceptance criteria
        stories_messages = user_stories_prompt.format_messages(**validated_inputs)
        stage2_out, attempts2 = await self._ainvoke_stage_structured(
            stage_name="user_stories",
            schema=UserStoriesAgentOutput,
            messages=stories_messages,
            max_retries=max_retries,
            max_output_tokens=stage_budget,
        )
        total_attempts += attempts2
        generated_stories = getattr(stage2_out, "user_stories", None) or []
        if not generated_stories:
            raise AISchemaValidationException(
                "Product planning stage 'user_stories' produced zero user stories.",
                provider=self.llm_service.provider_name,
            )

        # Stage 3: Technical specifications, success metrics, risks, and roadmap
        tech_messages = technical_specs_prompt.format_messages(**validated_inputs)
        stage3_out, attempts3 = await self._ainvoke_stage_structured(
            stage_name="technical_specifications",
            schema=TechnicalSpecsAgentOutput,
            messages=tech_messages,
            max_retries=max_retries,
            max_output_tokens=stage_budget,
        )
        total_attempts += attempts3
        generated_tech = getattr(stage3_out, "technical_requirements", None) or []
        generated_metrics = getattr(stage3_out, "success_metrics", None) or []
        generated_risks = getattr(stage3_out, "risk_analysis", None) or []
        generated_roadmap = getattr(stage3_out, "roadmap_recommendations", None) or []
        if not generated_tech:
            raise AISchemaValidationException(
                "Product planning stage 'technical_specifications' produced zero technical requirements.",
                provider=self.llm_service.provider_name,
            )

        # Stage 4: Combine generated sections & preserve verbatim evidence references
        combined_evidence = _merge_evidence_quotes(
            evidence,
            prd_doc.supporting_evidence,
            getattr(stage3_out, "supporting_evidence", []),
            [us.source_reference for us in generated_stories if getattr(us, "source_reference", None)],
        )
        prd_payload = prd_doc.model_dump()
        prd_payload["supporting_evidence"] = _merge_evidence_quotes(
            prd_doc.supporting_evidence,
            evidence,
        )

        # Stage 5: Validate assembled document against ProductPlanningAgentOutput Pydantic schema
        try:
            combined_output = ProductPlanningAgentOutput.model_validate(
                {
                    "feature_group_id": group_id,
                    "prd": prd_payload,
                    "user_stories": [s.model_dump() for s in generated_stories],
                    "technical_requirements": [t.model_dump() for t in generated_tech],
                    "success_metrics": [m.model_dump() for m in generated_metrics],
                    "risk_analysis": [r.model_dump() for r in generated_risks],
                    "roadmap_recommendations": [rp.model_dump() for rp in generated_roadmap],
                    "supporting_evidence": combined_evidence,
                }
            )
        except ValidationError as exc:
            raise AISchemaValidationException(
                f"Combined staged PRD document failed schema validation: {exc}",
                provider=self.llm_service.provider_name,
                original_exception=exc,
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
            attempts=total_attempts,
        )
        return AgentExecutionResult(data=combined_output, metadata=metadata)

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
        max_output_tokens: int = 950,
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

        validated_inputs = self.validate_input(inputs)
        messages = prd_generation_prompt.format_messages(**validated_inputs)
        result, _ = await self._ainvoke_stage_structured(
            stage_name="core_prd",
            schema=PRDAgentOutput,
            messages=messages,
            max_retries=max_retries,
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
        max_output_tokens: int = 950,
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

        validated_inputs = self.validate_input(inputs)
        messages = user_stories_prompt.format_messages(**validated_inputs)
        result, _ = await self._ainvoke_stage_structured(
            stage_name="user_stories",
            schema=UserStoriesAgentOutput,
            messages=messages,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
        return result.user_stories

    async def agenerate_technical_specs(
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
        max_output_tokens: int = 950,
    ) -> TechnicalSpecsAgentOutput:
        """
        Generates Stage 3 technical requirements, non-fabricated metrics, risks, and roadmap.
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

        validated_inputs = self.validate_input(inputs)
        messages = technical_specs_prompt.format_messages(**validated_inputs)
        result, _ = await self._ainvoke_stage_structured(
            stage_name="technical_specifications",
            schema=TechnicalSpecsAgentOutput,
            messages=messages,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
        return result
