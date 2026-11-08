"""
ProductMind AI — Feature Intelligence Agent Package
Exports specialist agent, service, prompts, schemas, and deterministic grouping engine.
"""

from app.ai.agents.feature_intelligence.agent import FeatureIntelligenceAgent
from app.ai.agents.feature_intelligence.service import FeatureIntelligenceService
from app.ai.agents.feature_intelligence.grouping import (
    filter_eligible_feature_requests,
    calculate_demand_metrics,
    validate_and_sanitize_groups,
    detect_lexical_duplicates,
)
from app.ai.agents.feature_intelligence.schemas import (
    FeatureRequestCandidate,
    FeatureGroupAnalysis,
    FeatureGroupingAgentOutput,
    FeatureGroupResult,
    DuplicateDetectionItem,
    DuplicateDetectionAgentOutput,
    GroupFeaturesRequest,
    GroupFeaturesResponse,
    DuplicateDetectionRequest,
    DuplicateDetectionResponse,
    DuplicateType,
    AnalysisStatus,
)
from app.ai.agents.feature_intelligence.prompts import (
    feature_grouping_prompt,
    duplicate_detection_prompt,
)

__all__ = [
    "FeatureIntelligenceAgent",
    "FeatureIntelligenceService",
    "filter_eligible_feature_requests",
    "calculate_demand_metrics",
    "validate_and_sanitize_groups",
    "detect_lexical_duplicates",
    "FeatureRequestCandidate",
    "FeatureGroupAnalysis",
    "FeatureGroupingAgentOutput",
    "FeatureGroupResult",
    "DuplicateDetectionItem",
    "DuplicateDetectionAgentOutput",
    "GroupFeaturesRequest",
    "GroupFeaturesResponse",
    "DuplicateDetectionRequest",
    "DuplicateDetectionResponse",
    "DuplicateType",
    "AnalysisStatus",
    "feature_grouping_prompt",
    "duplicate_detection_prompt",
]

