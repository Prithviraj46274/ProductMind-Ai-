"""
ProductMind AI — Prioritization Agent Package
Exports schemas, prompts, deterministic scoring engine, agent, and service.
"""

from app.ai.agents.prioritization.schemas import (
    PriorityLevel,
    FactorName,
    FactorWeightConfig,
    ThresholdConfig,
    ProductAnalyticsData,
    StrategicContext,
    FactorAssessment,
    PrioritizationAgentOutput,
    PrioritizationResult,
    AnalyzePrioritizationRequest,
    AnalyzePrioritizationResponse,
    RankPrioritizationRequest,
    RankPrioritizationResponse,
)
from app.ai.agents.prioritization.prompts import (
    PRIORITIZATION_SYSTEM_TEMPLATE,
    PRIORITIZATION_HUMAN_TEMPLATE,
    prioritization_prompt,
)
from app.ai.agents.prioritization.scoring import (
    compute_customer_demand_score,
    compute_urgency_score,
    compute_sentiment_score,
    compute_usage_impact_score,
    calculate_prioritization_score,
    rank_prioritization_results,
)
from app.ai.agents.prioritization.agent import (
    PrioritizationAgent,
    format_prioritization_prompt_inputs,
)
from app.ai.agents.prioritization.service import PrioritizationService

__all__ = [
    # Schemas & Configs
    "PriorityLevel",
    "FactorName",
    "FactorWeightConfig",
    "ThresholdConfig",
    "ProductAnalyticsData",
    "StrategicContext",
    "FactorAssessment",
    "PrioritizationAgentOutput",
    "PrioritizationResult",
    "AnalyzePrioritizationRequest",
    "AnalyzePrioritizationResponse",
    "RankPrioritizationRequest",
    "RankPrioritizationResponse",
    # Prompts
    "PRIORITIZATION_SYSTEM_TEMPLATE",
    "PRIORITIZATION_HUMAN_TEMPLATE",
    "prioritization_prompt",
    # Scoring Engine
    "compute_customer_demand_score",
    "compute_urgency_score",
    "compute_sentiment_score",
    "compute_usage_impact_score",
    "calculate_prioritization_score",
    "rank_prioritization_results",
    # Agent & Service
    "PrioritizationAgent",
    "format_prioritization_prompt_inputs",
    "PrioritizationService",
]

