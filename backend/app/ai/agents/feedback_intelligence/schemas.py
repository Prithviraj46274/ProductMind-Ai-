"""
ProductMind AI — Feedback Intelligence Agent Schemas
Defines structured domain enums, Pydantic v2 output schemas, validation constraints,
and API request/response contracts for the Feedback Intelligence Agent.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class FeedbackClassificationCategory(str, Enum):
    BUG = "Bug"
    FEATURE_REQUEST = "Feature Request"
    USABILITY = "Usability"
    PERFORMANCE = "Performance"
    SECURITY = "Security"
    INTEGRATION = "Integration"
    PRICING = "Pricing"
    GENERAL_FEEDBACK = "General Feedback"
    OTHER = "Other"


class FeedbackSentimentType(str, Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"
    MIXED = "Mixed"


class FeedbackUrgency(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ProductImpactArea(str, Enum):
    USER_EXPERIENCE = "User Experience"
    CUSTOMER_RETENTION = "Customer Retention"
    PRODUCT_ADOPTION = "Product Adoption"
    PERFORMANCE = "Performance"
    RELIABILITY = "Reliability"
    REVENUE = "Revenue"
    OPERATIONAL_EFFICIENCY = "Operational Efficiency"


class AnalysisStatus(str, Enum):
    COMPLETED = "completed"
    AMBIGUOUS = "ambiguous"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class FeedbackIntelligenceResult(BaseModel):
    """
    Strict, schema-enforced output produced by the Feedback Intelligence Agent.
    All assessments must be grounded strictly in customer feedback text.
    """
    feedback_id: str = Field(..., description="Target feedback identifier being analyzed")
    category: FeedbackClassificationCategory = Field(..., description="Primary classification category")
    secondary_tags: List[str] = Field(default_factory=list, description="Secondary categorization tags or descriptors")
    sentiment: FeedbackSentimentType = Field(..., description="Evaluated customer sentiment")
    sentiment_explanation: str = Field(..., min_length=5, description="Brief justification grounded in customer wording")
    urgency: FeedbackUrgency = Field(..., description="Operational urgency based on expressed pain or severity")
    urgency_explanation: str = Field(..., min_length=5, description="Evidence-based justification for urgency rating")
    main_theme: str = Field(..., min_length=3, description="Core customer topic or area of concern")
    subthemes: List[str] = Field(default_factory=list, description="Related thematic aspects")
    customer_pain_point: str = Field(..., min_length=5, description="Specific problem or obstacle encountered by the user")
    summary: str = Field(..., min_length=10, description="Concise synthesis of the feedback item")
    evidence: List[str] = Field(
        default_factory=list,
        description="Direct quotes or textual excerpts from the feedback supporting this analysis",
    )
    potential_product_impacts: List[ProductImpactArea] = Field(
        default_factory=list,
        description="Plausible product areas affected by this feedback",
    )
    suggested_action: str = Field(..., min_length=5, description="Recommended next action for the product team")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")
    analysis_status: AnalysisStatus = Field(
        default=AnalysisStatus.COMPLETED,
        description="Status flag indicating whether analysis was straightforward, ambiguous, or insufficient",
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Confidence score must be strictly between 0.0 and 1.0, got {v}")
        return round(v, 4)

    @model_validator(mode="after")
    def validate_evidence_and_status(self) -> "FeedbackIntelligenceResult":
        # If feedback was sufficient and completed, at least one piece of evidence is expected
        if self.analysis_status == AnalysisStatus.COMPLETED and not self.evidence:
            # Fall back to ambiguous if no concrete evidence was extracted
            self.analysis_status = AnalysisStatus.AMBIGUOUS
        # For insufficient information, ensure confidence is restrained
        if self.analysis_status == AnalysisStatus.INSUFFICIENT_INFORMATION and self.confidence > 0.5:
            self.confidence = 0.5
        return self


# -------------------------------------------------------------------------
# API Request / Response Schemas
# -------------------------------------------------------------------------

class FeedbackAnalysisRequest(BaseModel):
    """Optional parameters for initiating single feedback analysis."""
    force_reanalyze: bool = Field(
        default=False,
        description="Force re-running agent analysis even if previous analysis exists",
    )


class FeedbackAnalysisResponse(BaseModel):
    """API response model for single feedback analysis."""
    feedback_id: str
    workspace_id: str
    title: str
    analysis: FeedbackIntelligenceResult
    metadata: Dict[str, Any]
    analyzed_at: datetime


class BatchFeedbackAnalysisRequest(BaseModel):
    """Controlled batch analysis payload with concurrency bounds."""
    feedback_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of feedback identifiers to analyze (maximum 10 per request)",
    )
    force_reanalyze: bool = Field(default=False)


class BatchFeedbackItemResult(BaseModel):
    feedback_id: str
    status: str  # "success" or "error"
    analysis: Optional[FeedbackIntelligenceResult] = None
    error: Optional[str] = None


class BatchFeedbackAnalysisResponse(BaseModel):
    total_requested: int
    successful: int
    failed: int
    results: List[BatchFeedbackItemResult]

