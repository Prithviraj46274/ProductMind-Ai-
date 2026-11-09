"""
ProductMind AI — Product Planning Agent Schemas
Defines Pydantic v2 domain schemas for PRD generation, user stories, acceptance criteria,
technical requirements, success metrics, risk analysis, and roadmap recommendations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class RequirementOrigin(str, Enum):
    SOURCE_SUPPORTED = "source_supported"       # Grounded directly in original customer feedback / quotes
    USER_PROVIDED = "user_provided"             # Sourced from user-provided strategic context / instructions
    AI_RECOMMENDATION = "ai_recommendation"     # Proposed AI suggestion requiring human / engineering review
    ASSUMPTION = "assumption"                   # Working operational assumption requiring confirmation


class ScenarioType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    EDGE_CASE = "edge_case"


class TechnicalCategory(str, Enum):
    ARCHITECTURE = "architecture"
    API = "api"
    DATA = "data"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TESTING = "testing"


class MetricDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    MAINTAIN = "maintain"
    UNKNOWN = "unknown"


class RiskCategory(str, Enum):
    TECHNICAL = "technical"
    PRODUCT = "product"
    EXTERNAL = "external"
    ADOPTION = "adoption"
    DATA = "data"


class SeverityLevel(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Input Schemas
# ---------------------------------------------------------------------------

class ProductStrategicContext(BaseModel):
    """Optional user-supplied strategic and organizational context."""
    model_config = ConfigDict(extra="ignore")

    product_name: Optional[str] = Field(default=None, description="Name of the overarching product")
    product_description: Optional[str] = Field(default=None, description="Brief description of product domain")
    target_customer_segments: List[str] = Field(default_factory=list, description="Target customer tiers or industries")
    business_goals: List[str] = Field(default_factory=list, description="Overarching business goals")
    current_quarter_objectives: List[str] = Field(default_factory=list, description="Current quarter OKRs")
    technical_constraints: List[str] = Field(default_factory=list, description="Known architectural or tech constraints")
    known_dependencies: List[str] = Field(default_factory=list, description="Existing systems or upstream services")
    additional_planning_instructions: Optional[str] = Field(default=None, description="Custom PM guidance for planning")


# ---------------------------------------------------------------------------
# Granular Planning Document Schemas
# ---------------------------------------------------------------------------

class ProductRequirement(BaseModel):
    """Structured product requirement with explicit origin classification and evidence grounding."""
    model_config = ConfigDict(extra="ignore")

    requirement_id: str = Field(default="REQ-001", description="Unique requirement ID (e.g., 'REQ-001', 'NFR-001')")
    title: str = Field(..., description="Concise requirement title")
    description: str = Field(..., description="Clear specification of capability or constraint")
    origin: RequirementOrigin = Field(
        default=RequirementOrigin.AI_RECOMMENDATION,
        description="Origin classification: 'source_supported', 'user_provided', 'ai_recommendation', or 'assumption'",
    )
    is_confirmed: bool = Field(
        default=False,
        description="True ONLY if directly source-supported by feedback or user context. False for AI recommendations",
    )
    requires_confirmation: bool = Field(
        default=True,
        description="True if human PM or engineering review/confirmation is required",
    )
    numerical_threshold: Optional[str] = Field(
        default=None,
        description="Explicit numerical target (latency, SLA, capacity) ONLY if grounded in source. Null if unverified",
    )
    source_reference: Optional[str] = Field(
        default=None,
        description="Direct customer quote, feedback ID, or user directive grounding this requirement",
    )

    @model_validator(mode="before")
    @classmethod
    def parse_from_string(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {
                "requirement_id": "REQ-001",
                "title": data[:60],
                "description": data,
                "origin": RequirementOrigin.AI_RECOMMENDATION.value,
                "is_confirmed": False,
                "requires_confirmation": True,
                "numerical_threshold": None,
                "source_reference": None,
            }
        return data


class ProductRequirementsDocument(BaseModel):
    """Comprehensive, structured Product Requirements Document."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Clear, descriptive PRD title")
    executive_summary: str = Field(..., description="High-level overview of the feature and value proposition")
    problem_statement: str = Field(..., description="Precise formulation of customer and business problems solved")
    background: str = Field(..., description="Origin of request, customer demand context, and historical drivers")
    customer_pain_points: List[str] = Field(default_factory=list, description="Specific grounded customer pain points")
    target_users: List[str] = Field(default_factory=list, description="Target personas and primary user roles")
    business_objectives: List[str] = Field(default_factory=list, description="Commercial and product goals achieved")
    proposed_solution: str = Field(..., description="Detailed description of the proposed capability and user experience")
    functional_requirements: List[ProductRequirement] = Field(default_factory=list, description="Explicit functional system capabilities classified by origin")
    non_functional_requirements: List[ProductRequirement] = Field(default_factory=list, description="Performance, reliability, security requirements with ungrounded thresholds marked unconfirmed")
    workflows: List[str] = Field(default_factory=list, description="Step-by-step user-facing operational workflows")
    dependencies: List[str] = Field(default_factory=list, description="System, API, or external service dependencies")
    risks_and_assumptions: List[str] = Field(default_factory=list, description="Key operational assumptions and known risks")
    success_metrics: List[str] = Field(default_factory=list, description="Primary metrics to evaluate feature success")
    out_of_scope: List[str] = Field(default_factory=list, description="Explicitly deferred capabilities or non-goals")
    open_questions: List[str] = Field(default_factory=list, description="Unresolved decisions requiring team alignment")
    supporting_evidence: List[str] = Field(default_factory=list, description="Direct customer feedback quotes backing this PRD")


class AcceptanceCriterion(BaseModel):
    """Measurable test criterion with Given/When/Then formatting."""
    model_config = ConfigDict(extra="ignore")

    criterion_id: str = Field(..., description="Unique criterion ID (e.g., 'AC-001')")
    description: str = Field(..., description="Given-When-Then behavioral specification")
    scenario_type: str = Field(default="positive", description="positive, negative, or edge_case")
    testable: bool = Field(default=True, description="Whether criterion is independently verifiable")
    origin: RequirementOrigin = Field(default=RequirementOrigin.AI_RECOMMENDATION, description="Origin classification")
    is_confirmed: bool = Field(default=False, description="True only if directly source-supported")
    requires_confirmation: bool = Field(default=True, description="True if requires PM/eng review")
    related_story_id: Optional[str] = Field(default=None, description="Parent user story ID")


class UserStory(BaseModel):
    """Agile User Story adhering to 'As a... I want... So that...' format."""
    model_config = ConfigDict(extra="ignore")

    story_id: str = Field(..., description="Unique story ID (e.g., 'US-001')")
    title: str = Field(..., description="Concise story title")
    description: str = Field(..., description="As a [persona], I want [capability], so that [benefit]")
    persona: str = Field(..., description="Target persona benefiting from this story")
    business_value: str = Field(..., description="Direct customer or commercial value delivered")
    priority: str = Field(default="High", description="Critical, High, Medium, or Low")
    origin: RequirementOrigin = Field(default=RequirementOrigin.SOURCE_SUPPORTED, description="Origin classification")
    is_confirmed: bool = Field(default=True, description="True if derived directly from customer feedback")
    requires_confirmation: bool = Field(default=False, description="True if AI-proposed story needing confirmation")
    related_requirements: List[str] = Field(default_factory=list, description="Associated functional requirement IDs or descriptions")
    acceptance_criteria: List[AcceptanceCriterion] = Field(default_factory=list, description="Measurable acceptance criteria")
    dependencies: List[str] = Field(default_factory=list, description="Pre-requisite user stories or technical blockers")
    supporting_feedback_ids: List[str] = Field(default_factory=list, description="Traceable original customer feedback IDs")
    source_reference: Optional[str] = Field(default=None, description="Feedback quote or customer pain point reference")


class TechnicalRequirement(BaseModel):
    """Proposed engineering requirement labeled for human engineering review."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Clear engineering requirement title")
    description: str = Field(..., description="Technical specification or architectural suggestion")
    category: str = Field(default="architecture", description="architecture, api, data, security, performance, or testing")
    rationale: str = Field(..., description="Why this engineering approach is proposed")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="AI confidence in proposal")
    requires_engineering_review: bool = Field(default=True, description="Always requires engineering validation")
    origin: RequirementOrigin = Field(default=RequirementOrigin.AI_RECOMMENDATION, description="user_provided if from technical constraints, else ai_recommendation")
    is_confirmed: bool = Field(default=False, description="True only if from user-provided technical constraints")
    source_reference: Optional[str] = Field(default=None, description="User technical constraint reference if applicable")


# ---------------------------------------------------------------------------
# Metric Direction Inference Helper
# ---------------------------------------------------------------------------

def infer_expected_direction(
    metric_name: str,
    description: Optional[str] = None,
    suggested_target: Optional[str] = None,
    current_direction: Optional[str] = None,
) -> Optional[str]:
    """
    Deterministically infers or corrects the expected direction of a metric.
    - Decreasing: churn, error rates, latency, downtime, defects, failure rates, costs, bounce.
    - Increasing: adoption, retention, CSAT, NPS, throughput, engagement, speed, uptime.
    - Maintaining: maintain, keep steady, baseline stability.
    - Unknown/Unclassified: returns None (never assumes 'increase') and flags for human confirmation.
    """
    combined = f"{metric_name} {description or ''} {suggested_target or ''}".lower()

    # Explicit keywords indicating reduction/decrease
    if any(k in combined for k in [
        "churn", "error rate", "latency", "downtime", "failure rate", "defect rate",
        "bounce rate", "drop rate", "bug count", "incident count", "load time", "response time",
        "cost reduction"
    ]):
        return "decrease"
    if any(combined.startswith(p) or f" {p} " in combined for p in [
        "reduce", "reduction", "decrease", "lower", "cut", "minimize", "minimise"
    ]):
        return "decrease"

    # Explicit keywords indicating maintain/stabilize (checked before general increase keywords)
    if any(k in combined for k in ["maintain", "keep constant", "steady", "stability"]):
        return "maintain"
    if any(combined.startswith(p) or f" {p} " in combined for p in [
        "maintain", "keep", "stabilize", "stabilise"
    ]):
        return "maintain"

    # Explicit keywords indicating increase/improvement
    if any(k in combined for k in [
        "adoption", "retention", "csat", "nps", "satisfaction", "conversion",
        "uptime", "availability", "throughput", "engagement", "active accounts",
        "active users", "weekly users", "export users", "users", "growth", "revenue"
    ]):
        return "increase"
    if any(combined.startswith(p) or f" {p} " in combined for p in [
        "increase", "improve", "boost", "grow", "expand", "maximize", "maximise"
    ]):
        return "increase"

    if current_direction == "maintain":
        return "maintain"

    # Do NOT assume increase! Return None for unknown/unclassified metrics.
    return None


class SuccessMetric(BaseModel):
    """Measurable product metric. Never fabricates baselines or unsupported commitments."""
    model_config = ConfigDict(extra="ignore")

    metric_name: str = Field(..., description="Name of the key performance indicator")
    description: str = Field(..., description="Explanation of what is measured and why")
    measurement_method: str = Field(..., description="How data will be collected or computed")
    expected_direction: Optional[str] = Field(default=None, description="increase, decrease, maintain, or None if unclassified/unknown")
    direction_requires_confirmation: bool = Field(default=False, description="True if metric direction is unknown/unclassified and requires PM confirmation")
    baseline: Optional[str] = Field(default=None, description="Current baseline value if known, else null (never fabricated)")
    suggested_target: Optional[str] = Field(default=None, description="Proposed target awaiting business confirmation, or null if unestablished")
    data_source: Optional[str] = Field(default=None, description="Analytics system or database table tracking this metric")
    measurement_period: Optional[str] = Field(default=None, description="Evaluation timeframe (e.g., '30 days post-launch')")
    requires_confirmation: bool = Field(default=True, description="Requires confirmation before being an official KPI")
    origin: RequirementOrigin = Field(default=RequirementOrigin.AI_RECOMMENDATION, description="Origin classification of metric definition")
    is_confirmed: bool = Field(default=False, description="True only if KPI is from established business goals or source data")
    source_reference: Optional[str] = Field(default=None, description="Strategic context or analytics reference if applicable")
    target_origin: Optional[RequirementOrigin] = Field(default=None, description="Origin of suggested_target (user_provided, source_supported, ai_recommendation, or None)")
    is_target_confirmed: bool = Field(default=False, description="True only if target was explicitly provided by user or analytics")
    requires_target_confirmation: bool = Field(default=True, description="True if target is an unconfirmed AI proposal or unmeasured")
    is_period_confirmed: bool = Field(default=False, description="True only if measurement period was explicitly provided by user or source")
    period_requires_confirmation: bool = Field(default=True, description="True if measurement period is an AI recommendation requiring confirmation")

    @model_validator(mode="after")
    def validate_metric_targets_and_origins(self) -> "SuccessMetric":
        # 0. Deterministic direction consistency check
        inferred = infer_expected_direction(
            metric_name=self.metric_name,
            description=self.description,
            suggested_target=self.suggested_target,
            current_direction=self.expected_direction,
        )
        if inferred is not None:
            self.expected_direction = inferred
            self.direction_requires_confirmation = False
        else:
            self.expected_direction = None
            self.direction_requires_confirmation = True

        # 1. suggested_target validation & origin resolution
        if self.suggested_target:
            if self.target_origin is None:
                if self.origin == RequirementOrigin.USER_PROVIDED and self.is_confirmed:
                    self.target_origin = RequirementOrigin.USER_PROVIDED
                    self.is_target_confirmed = True
                    self.requires_target_confirmation = False
                elif self.origin == RequirementOrigin.SOURCE_SUPPORTED and self.is_confirmed:
                    self.target_origin = RequirementOrigin.SOURCE_SUPPORTED
                    self.is_target_confirmed = True
                    self.requires_target_confirmation = False
                else:
                    self.target_origin = RequirementOrigin.AI_RECOMMENDATION
                    self.is_target_confirmed = False
                    self.requires_target_confirmation = True
            elif self.target_origin == RequirementOrigin.AI_RECOMMENDATION:
                # Enforce: AI recommendations can NEVER be confirmed commitments
                self.is_target_confirmed = False
                self.requires_target_confirmation = True
            elif self.target_origin in (RequirementOrigin.USER_PROVIDED, RequirementOrigin.SOURCE_SUPPORTED):
                # Cannot confirm without source reference
                if not self.source_reference:
                    self.target_origin = RequirementOrigin.AI_RECOMMENDATION
                    self.is_target_confirmed = False
                    self.requires_target_confirmation = True
                else:
                    self.is_target_confirmed = True
                    self.requires_target_confirmation = False
        else:
            self.target_origin = None
            self.is_target_confirmed = False
            self.requires_target_confirmation = False

        # 2. measurement_period validation
        if self.measurement_period:
            if self.origin not in (RequirementOrigin.USER_PROVIDED, RequirementOrigin.SOURCE_SUPPORTED) or not self.is_confirmed or not self.source_reference:
                self.is_period_confirmed = False
                self.period_requires_confirmation = True
            else:
                self.is_period_confirmed = True
                self.period_requires_confirmation = False
        else:
            self.is_period_confirmed = False
            self.period_requires_confirmation = False

        # 3. Overall metric confirmation validation
        if self.origin == RequirementOrigin.AI_RECOMMENDATION:
            self.is_confirmed = False
            self.requires_confirmation = True
        elif self.origin in (RequirementOrigin.USER_PROVIDED, RequirementOrigin.SOURCE_SUPPORTED):
            if not self.source_reference:
                # Missing reference downgrades to AI recommendation
                self.origin = RequirementOrigin.AI_RECOMMENDATION
                self.is_confirmed = False
                self.requires_confirmation = True

        return self


class RiskItem(BaseModel):
    """Identified project, product, or adoption risk with mitigations."""
    model_config = ConfigDict(extra="ignore")

    description: str = Field(..., description="Clear explanation of the risk event")
    category: str = Field(default="technical", description="technical, product, external, adoption, or data")
    impact: str = Field(default="Medium", description="Critical, High, Medium, or Low")
    likelihood: str = Field(default="Medium", description="High, Medium, or Low")
    mitigation: str = Field(..., description="Actionable strategy to eliminate or reduce the risk")
    requires_human_review: bool = Field(default=True, description="Flag indicating human PM/Eng sign-off needed")


class RoadmapPhase(BaseModel):
    """Recommended progressive delivery phase."""
    model_config = ConfigDict(extra="ignore")

    phase_name: str = Field(..., description="Phase identifier (e.g., 'Phase 1 – Foundation')")
    objective: str = Field(..., description="Primary milestone goal of this delivery phase")
    tasks: List[str] = Field(default_factory=list, description="Recommended engineering and design tasks")
    dependencies: List[str] = Field(default_factory=list, description="Pre-requisite phases or external integrations")
    deliverables: List[str] = Field(default_factory=list, description="Tangible artifacts and deployed features")
    suggested_sequencing: int = Field(default=1, ge=1, description="Numerical order of execution")
    risks: List[str] = Field(default_factory=list, description="Phase-specific execution risks")


# ---------------------------------------------------------------------------
# LLM Structured Output Envelopes
# ---------------------------------------------------------------------------

class ProductPlanningAgentOutput(BaseModel):
    """Complete structured output from ProductPlanningAgent."""
    model_config = ConfigDict(extra="ignore")

    feature_group_id: str = Field(..., description="Source feature group ID")
    prd: ProductRequirementsDocument = Field(..., description="Full Product Requirements Document")
    user_stories: List[UserStory] = Field(default_factory=list, description="Generated user stories with acceptance criteria")
    technical_requirements: List[TechnicalRequirement] = Field(default_factory=list, description="Proposed engineering suggestions")
    success_metrics: List[SuccessMetric] = Field(default_factory=list, description="Recommended KPIs with non-fabricated baselines")
    risk_analysis: List[RiskItem] = Field(default_factory=list, description="Categorized risks and actionable mitigations")
    roadmap_recommendations: List[RoadmapPhase] = Field(default_factory=list, description="Suggested delivery milestones")
    supporting_evidence: List[str] = Field(default_factory=list, description="Verbatim customer feedback quotes")


class PRDAgentOutput(BaseModel):
    """Target schema when generating or regenerating PRD alone."""
    model_config = ConfigDict(extra="ignore")

    feature_group_id: str = Field(..., description="Source feature group ID")
    prd: ProductRequirementsDocument = Field(..., description="Generated Product Requirements Document")


class UserStoriesAgentOutput(BaseModel):
    """Target schema when generating or regenerating user stories alone."""
    model_config = ConfigDict(extra="ignore")

    feature_group_id: str = Field(..., description="Source feature group ID")
    user_stories: List[UserStory] = Field(default_factory=list, description="Generated user stories")


# ---------------------------------------------------------------------------
# API Request & Response Models
# ---------------------------------------------------------------------------

class GenerateProductPlanRequest(BaseModel):
    """Request payload to generate a comprehensive product plan."""
    model_config = ConfigDict(extra="ignore")

    workspace_id: str = Field(..., description="Target workspace ID")
    feature_group_id: str = Field(..., description="FeatureGroup ObjectId to plan")
    prioritization_result_id: Optional[str] = Field(default=None, description="Optional PrioritizationScenario ID")
    strategic_context: Optional[ProductStrategicContext] = Field(default=None, description="Optional organizational context")
    force_approved_overwrite: bool = Field(default=False, description="Explicit authorization to overwrite an already approved PRD")


class GeneratePRDRequest(BaseModel):
    """Request payload to generate or regenerate the PRD only."""
    model_config = ConfigDict(extra="ignore")

    workspace_id: str = Field(..., description="Target workspace ID")
    feature_group_id: str = Field(..., description="FeatureGroup ObjectId")
    planning_id: Optional[str] = Field(default=None, description="Optional existing PRD/Planning ID to update")
    strategic_context: Optional[ProductStrategicContext] = Field(default=None)
    force_approved_overwrite: bool = Field(default=False)


class GenerateUserStoriesRequest(BaseModel):
    """Request payload to generate or regenerate user stories only."""
    model_config = ConfigDict(extra="ignore")

    workspace_id: str = Field(..., description="Target workspace ID")
    feature_group_id: str = Field(..., description="FeatureGroup ObjectId")
    planning_id: Optional[str] = Field(default=None, description="Optional existing PRD/Planning ID to attach stories to")
    strategic_context: Optional[ProductStrategicContext] = Field(default=None)
    force_approved_overwrite: bool = Field(default=False)


class ReviewPlanRequest(BaseModel):
    """Request payload to update the review state of a plan."""
    model_config = ConfigDict(extra="ignore")

    review_status: str = Field(..., description="'pending_review', 'approved', 'rejected', or 'draft'")
    review_notes: Optional[str] = Field(default=None, description="Optional feedback or rejection reasoning")


class ProductPlanResponse(BaseModel):
    """Full API response for a persisted Product Planning record."""
    model_config = ConfigDict(extra="ignore")

    planning_id: str = Field(..., description="PRD document ObjectId")
    workspace_id: str = Field(..., description="Workspace ID")
    feature_group_id: str = Field(..., description="FeatureGroup ID")
    prioritization_result_id: Optional[str] = Field(default=None)
    title: str = Field(...)
    version: str = Field(default="1.0.0")
    status: str = Field(...)
    prd: Optional[ProductRequirementsDocument] = None
    user_stories: List[UserStory] = Field(default_factory=list)
    technical_requirements: List[TechnicalRequirement] = Field(default_factory=list)
    success_metrics: List[SuccessMetric] = Field(default_factory=list)
    risk_analysis: List[RiskItem] = Field(default_factory=list)
    roadmap_recommendations: List[RoadmapPhase] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    ai_metadata: Optional[Dict[str, Any]] = None
    review_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
