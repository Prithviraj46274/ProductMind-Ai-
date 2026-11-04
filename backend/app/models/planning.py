"""
ProductMind AI — Planning, Prioritization, PRD, Roadmap & Release Domain Models
Matches Mongoose schemas for Feature, PRD, RoadmapItem, Release, Experiment, Journey, and Scenarios.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator, ConfigDict
from bson import ObjectId

from app.models.base import BaseMongoModel, utc_now
from app.database.objectid import PyObjectId
from app.core.enums import (
    FeatureStatus,
    PriorityTier,
    PRDStatus,
    RoadmapStatus,
    ReleaseStatus,
    ExperimentStatus,
    ExperimentConclusion,
    FeedbackPriority,
    FeedbackSentiment,
    calculate_priority_score,
    get_priority_tier,
)


class FeatureComment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    author: str
    author_id: Optional[PyObjectId] = Field(default=None, alias="authorId")
    text: str = Field(..., max_length=1000)
    created_at: Optional[datetime] = Field(default_factory=utc_now, alias="createdAt")


class Feature(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    feature_group_id: Optional[PyObjectId] = Field(default=None, alias="featureGroupId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    name: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., max_length=5000)
    customer_impact: float = Field(default=5.0, alias="customerImpact", ge=1.0, le=10.0)
    urgency: float = Field(default=5.0, ge=1.0, le=10.0)
    demand: float = Field(default=5.0, ge=1.0, le=10.0)
    business_value: float = Field(default=5.0, alias="businessValue", ge=1.0, le=10.0)
    score: float = Field(default=5.0, ge=1.0, le=10.0)
    priority_tier: PriorityTier = Field(default=PriorityTier.MEDIUM, alias="priorityTier")
    status: FeatureStatus = Field(default=FeatureStatus.IN_PLANNING)
    owner: Optional[str] = Field(default=None, max_length=100)
    owner_id: Optional[PyObjectId] = Field(default=None, alias="ownerId")
    target_release: Optional[str] = Field(default=None, alias="targetRelease", max_length=50)
    comments: List[FeatureComment] = Field(default_factory=list)
    ai_justification: str = Field(default="", alias="aiJustification", max_length=1500)
    is_manual_override: bool = Field(default=False, alias="isManualOverride")

    @model_validator(mode="after")
    def compute_score_and_tier(self) -> "Feature":
        if not self.is_manual_override:
            # Only compute score if not provided or default
            if self.score == 5.0:
                computed_score = calculate_priority_score(
                    customer_impact=self.customer_impact,
                    urgency=self.urgency,
                    demand=self.demand,
                    business_value=self.business_value,
                )
                object.__setattr__(self, "score", computed_score)
            object.__setattr__(self, "priority_tier", get_priority_tier(self.score))
        return self


class PRDSections(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    overview: str = ""
    problem_statement: str = Field(default="", alias="problemStatement")
    target_users: str = Field(default="", alias="targetUsers")
    customer_pain_points: str = Field(default="", alias="customerPainPoints")
    proposed_solution: str = Field(default="", alias="proposedSolution")
    goals_and_success_metrics: str = Field(default="", alias="goalsAndSuccessMetrics")
    functional_requirements: str = Field(default="", alias="functionalRequirements")
    non_functional_requirements: str = Field(default="", alias="nonFunctionalRequirements")
    user_stories: str = Field(default="", alias="userStories")
    acceptance_criteria: str = Field(default="", alias="acceptanceCriteria")
    dependencies_and_constraints: str = Field(default="", alias="dependenciesAndConstraints")
    risks_and_mitigations: str = Field(default="", alias="risksAndMitigations")
    release_plan: str = Field(default="", alias="releasePlan")


class PRD(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    feature_id: Optional[PyObjectId] = Field(default=None, alias="featureId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    title: str = Field(..., min_length=3, max_length=200)
    version: str = Field(default="1.0.0")
    status: PRDStatus = Field(default=PRDStatus.DRAFT)
    author: Optional[str] = None
    author_id: Optional[PyObjectId] = Field(default=None, alias="authorId")
    sections: PRDSections = Field(default_factory=PRDSections)
    ai_generated: bool = Field(default=False, alias="aiGenerated")


class RoadmapItem(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    feature_id: Optional[PyObjectId] = Field(default=None, alias="featureId")
    release_id: Optional[PyObjectId] = Field(default=None, alias="releaseId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)
    status: RoadmapStatus = Field(default=RoadmapStatus.PLANNED)
    priority: FeedbackPriority = Field(default=FeedbackPriority.MEDIUM)
    owner: Optional[str] = None
    owner_id: Optional[PyObjectId] = Field(default=None, alias="ownerId")
    start_date: str = Field(..., alias="startDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    target_date: str = Field(..., alias="targetDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    milestone: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    dependencies: List[PyObjectId] = Field(default_factory=list)
    notes: str = Field(default="", max_length=1500)


class ReleaseChecklistItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    title: str
    completed: bool = False
    required: bool = True


class Release(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    name: str = Field(..., max_length=150)
    version: str = Field(..., max_length=50)
    description: str = Field(default="", max_length=2000)
    planned_date: str = Field(..., alias="plannedDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    owner: Optional[str] = None
    owner_id: Optional[PyObjectId] = Field(default=None, alias="ownerId")
    status: ReleaseStatus = Field(default=ReleaseStatus.IN_PROGRESS)
    included_feature_ids: List[PyObjectId] = Field(default_factory=list, alias="includedFeatureIds")
    roadmap_item_ids: List[PyObjectId] = Field(default_factory=list, alias="roadmapItemIds")
    checklist: List[ReleaseChecklistItem] = Field(default_factory=list)
    release_notes: str = Field(default="", alias="releaseNotes")

    @property
    def readiness_percent(self) -> int:
        if not self.checklist:
            return 0
        completed = sum(1 for c in self.checklist if c.completed)
        return int(round((completed / len(self.checklist)) * 100))

    @property
    def is_gated(self) -> bool:
        if not self.checklist:
            return True
        return any(c.required and not c.completed for c in self.checklist)


class ProductExperiment(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    name: str = Field(..., max_length=150)
    problem: str = Field(default="", max_length=1500)
    hypothesis: str = Field(..., max_length=2000)
    target_audience: str = Field(default="All active users", alias="targetAudience", max_length=200)
    proposed_change: str = Field(default="", alias="proposedChange", max_length=1500)
    success_metric: str = Field(..., alias="successMetric", max_length=120)
    baseline: float = Field(default=0.0)
    target: float = Field(default=0.0)
    observed_value: Optional[float] = Field(default=None, alias="observedValue")
    start_date: str = Field(..., alias="startDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., alias="endDate", pattern=r"^\d{4}-\d{2}-\d{2}$")
    linked_feature_id: Optional[PyObjectId] = Field(default=None, alias="linkedFeatureId")
    owner: Optional[str] = None
    owner_id: Optional[PyObjectId] = Field(default=None, alias="ownerId")
    status: ExperimentStatus = Field(default=ExperimentStatus.RUNNING)
    conclusion: ExperimentConclusion = Field(default=ExperimentConclusion.CONTINUE)
    notes: str = Field(default="", max_length=2000)


class Touchpoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    name: str
    sentiment: FeedbackSentiment = Field(default=FeedbackSentiment.POSITIVE)
    pain_points: str = Field(default="", alias="painPoints")
    opportunity: str = ""


class CustomerJourney(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    name: str = Field(..., max_length=100)
    order: int = Field(..., ge=1, le=10)
    description: str = Field(default="", max_length=1500)
    touchpoints: List[Touchpoint] = Field(default_factory=list)


class AdjustedFeature(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, extra="ignore")
    feature_id: PyObjectId = Field(..., alias="featureId")
    customer_impact: float = Field(..., alias="customerImpact", ge=1.0, le=10.0)
    urgency: float = Field(..., ge=1.0, le=10.0)
    demand: float = Field(..., ge=1.0, le=10.0)
    business_value: float = Field(..., alias="businessValue", ge=1.0, le=10.0)
    simulated_score: Optional[float] = Field(default=None, alias="simulatedScore")

    @model_validator(mode="after")
    def compute_simulated_score(self) -> "AdjustedFeature":
        if self.simulated_score is None:
            self.simulated_score = calculate_priority_score(
                customer_impact=self.customer_impact,
                urgency=self.urgency,
                demand=self.demand,
                business_value=self.business_value,
            )
        return self


class PrioritizationScenario(BaseMongoModel):
    workspace_id: PyObjectId = Field(..., alias="workspaceId")
    legacy_id: Optional[str] = Field(default=None, alias="legacyId", max_length=120)
    name: str = Field(..., max_length=150)
    description: str = Field(default="", max_length=1500)
    created_by: Optional[PyObjectId] = Field(default=None, alias="createdBy")
    adjusted_features: List[AdjustedFeature] = Field(default_factory=list, alias="adjustedFeatures")
