"""
ProductMind AI — Product Planning Agent Package
Exports schemas, prompts, agent, and service for transforming prioritized feature
groups into evidence-backed PRDs, user stories, acceptance criteria, and roadmaps.
"""

from app.ai.agents.product_planning.schemas import (
    RequirementOrigin,
    ProductRequirement,
    infer_expected_direction,
    ScenarioType,
    TechnicalCategory,
    MetricDirection,
    RiskCategory,
    SeverityLevel,
    ReviewStatus,
    ProductStrategicContext,
    ProductRequirementsDocument,
    AcceptanceCriterion,
    UserStory,
    TechnicalRequirement,
    SuccessMetric,
    RiskItem,
    RoadmapPhase,
    ProductPlanningAgentOutput,
    PRDAgentOutput,
    UserStoriesAgentOutput,
    GenerateProductPlanRequest,
    GeneratePRDRequest,
    GenerateUserStoriesRequest,
    ReviewPlanRequest,
    ProductPlanResponse,
)
from app.ai.agents.product_planning.prompts import (
    product_planning_prompt,
    prd_generation_prompt,
    user_stories_prompt,
)
from app.ai.agents.product_planning.agent import (
    ProductPlanningAgent,
    format_product_planning_prompt_inputs,
)
from app.ai.agents.product_planning.service import (
    ProductPlanningService,
    build_prd_sections,
)

__all__ = [
    # Schemas
    "RequirementOrigin",
    "ProductRequirement",
    "infer_expected_direction",
    "ScenarioType",
    "TechnicalCategory",
    "MetricDirection",
    "RiskCategory",
    "SeverityLevel",
    "ReviewStatus",
    "ProductStrategicContext",
    "ProductRequirementsDocument",
    "AcceptanceCriterion",
    "UserStory",
    "TechnicalRequirement",
    "SuccessMetric",
    "RiskItem",
    "RoadmapPhase",
    "ProductPlanningAgentOutput",
    "PRDAgentOutput",
    "UserStoriesAgentOutput",
    "GenerateProductPlanRequest",
    "GeneratePRDRequest",
    "GenerateUserStoriesRequest",
    "ReviewPlanRequest",
    "ProductPlanResponse",
    # Prompts
    "product_planning_prompt",
    "prd_generation_prompt",
    "user_stories_prompt",
    # Agent & Helper
    "ProductPlanningAgent",
    "format_product_planning_prompt_inputs",
    # Service & Helper
    "ProductPlanningService",
    "build_prd_sections",
]

