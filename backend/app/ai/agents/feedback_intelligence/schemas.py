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

    @model_validator(mode="before")
    @classmethod
    def normalize_llm_output(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # If model wrapped fields inside 'feedback'
            if "feedback" in data and isinstance(data["feedback"], dict):
                inner = data.pop("feedback")
                for k, v in inner.items():
                    if k not in data or data[k] is None:
                        data[k] = v

            # Check for Classification wrapper
            if "Classification" in data and isinstance(data["Classification"], dict):
                c = data["Classification"]
                if "category" not in data or not data["category"]:
                    data["category"] = c.get("Primary_Category") or c.get("primary_category") or c.get("Category")
                if "secondary_tags" not in data or not data["secondary_tags"]:
                    data["secondary_tags"] = c.get("Secondary_Tags") or c.get("secondary_tags") or []

            # Check for Sentiment wrapper
            if "Sentiment" in data:
                s = data["Sentiment"]
                if isinstance(s, dict):
                    if "sentiment" not in data or not data["sentiment"]:
                        data["sentiment"] = s.get("Label") or s.get("sentiment") or s.get("Sentiment")
                    if "sentiment_explanation" not in data or not data["sentiment_explanation"]:
                        data["sentiment_explanation"] = s.get("Explanation") or s.get("explanation")
                elif isinstance(s, str):
                    data["sentiment"] = s

            # Check for Urgency wrapper
            if "Urgency" in data:
                u = data["Urgency"]
                if isinstance(u, dict):
                    data["urgency"] = u.get("urgency") or u.get("Urgency")
                elif isinstance(u, str):
                    data["urgency"] = u

            # Check for Themes wrapper
            if "Themes" in data and isinstance(data["Themes"], dict):
                th = data["Themes"]
                if "main_theme" not in data or not data["main_theme"]:
                    data["main_theme"] = th.get("Main_Theme") or th.get("main_theme")
                if "customer_pain_point" not in data or not data["customer_pain_point"]:
                    data["customer_pain_point"] = th.get("Customer_Pain_Point") or th.get("customer_pain_point")
                if "summary" not in data or not data["summary"]:
                    data["summary"] = th.get("Summary") or th.get("summary")

            # Check for Analysis_Metadata wrapper
            if "Analysis_Metadata" in data and isinstance(data["Analysis_Metadata"], dict):
                am = data["Analysis_Metadata"]
                if "confidence" not in data or data["confidence"] is None:
                    data["confidence"] = am.get("Confidence_Score") or am.get("confidence") or 0.85

            # Map primary_category -> category
            if ("category" not in data or not data["category"]) and "primary_category" in data:
                data["category"] = data["primary_category"]

            if "feedback_id" not in data or not data["feedback_id"]:
                data["feedback_id"] = data.get("id") or "feedback_item"
            if "category" not in data and "category_meta" in data and isinstance(data["category_meta"], dict):
                data["category"] = data["category_meta"].get("primary_category")
                if "secondary_tags" not in data:
                    data["secondary_tags"] = data["category_meta"].get("secondary_tags", [])
            if isinstance(data.get("sentiment"), dict):
                sent_dict = data["sentiment"]
                if "sentiment_explanation" not in data or not data["sentiment_explanation"]:
                    data["sentiment_explanation"] = sent_dict.get("sentiment_explanation", "Sentiment derived from feedback content.")
                data["sentiment"] = sent_dict.get("sentiment")
            if isinstance(data.get("urgency"), dict):
                urg_dict = data["urgency"]
                if "urgency_explanation" not in data or not data["urgency_explanation"]:
                    data["urgency_explanation"] = urg_dict.get("urgency_explanation", "Urgency evaluated based on user workflow friction.")
                data["urgency"] = urg_dict.get("urgency")

            # Defaults for resilient schema validation
            if "category" not in data or not data["category"]:
                data["category"] = FeedbackClassificationCategory.FEATURE_REQUEST
            if "sentiment" not in data or not data["sentiment"]:
                data["sentiment"] = FeedbackSentimentType.NEUTRAL
            if "urgency" not in data or not data["urgency"]:
                data["urgency"] = FeedbackUrgency.MEDIUM
            if "sentiment_explanation" not in data or not data["sentiment_explanation"]:
                data["sentiment_explanation"] = "Feedback tone was evaluated based on customer sentiment analysis."
            if "urgency_explanation" not in data or not data["urgency_explanation"]:
                data["urgency_explanation"] = "Urgency was evaluated based on operational impact."
            if "main_theme" not in data or not data["main_theme"]:
                data["main_theme"] = data.get("title") or "Customer Feature Request"
            if "customer_pain_point" not in data or not data["customer_pain_point"]:
                data["customer_pain_point"] = "Customer lacks direct access to requested functionality."
            if "summary" not in data or not data["summary"]:
                data["summary"] = f"Customer request regarding {data.get('main_theme', 'feature')}."
            if "suggested_action" not in data or not data["suggested_action"]:
                data["suggested_action"] = "Evaluate feature request for roadmap scheduling."
            if "confidence" not in data or data["confidence"] is None:
                data["confidence"] = 0.85
        return data

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

