"""
ProductMind AI — Deterministic Prioritization Scoring Engine
Implements mathematically rigorous, explainable factor normalization, reweighting
for missing analytics, deterministic composite scoring, and feature ranking.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.ai.agents.prioritization.schemas import (
    FactorName,
    FactorWeightConfig,
    ThresholdConfig,
    ProductAnalyticsData,
    PriorityLevel,
    PrioritizationResult,
)


def compute_customer_demand_score(
    feedback_count: int,
    unique_customer_count: int,
) -> float:
    """
    Computes a normalized customer demand score (0.0 to 100.0) based on
    distinct requesting accounts and total request volume.
    Emphasizes broad cross-customer demand while rewarding repeated requests.
    """
    if unique_customer_count <= 0 and feedback_count <= 0:
        return 0.0

    # 1. Breadth: Each unique customer provides up to 20 pts (max 80 pts for 4+ accounts)
    breadth_score = min(80.0, unique_customer_count * 20.0)

    # 2. Depth: Repeat requests from existing customers add 5 pts each (max 20 pts)
    repeat_requests = max(0, feedback_count - unique_customer_count)
    depth_score = min(20.0, repeat_requests * 5.0)

    total_score = breadth_score + depth_score
    return round(min(100.0, max(0.0, total_score)), 2)


def compute_urgency_score(urgency_distribution: Dict[str, int]) -> float:
    """
    Computes a normalized operational urgency score (0.0 to 100.0)
    using weighted customer urgency ratings:
    - Critical: 100.0
    - High: 75.0
    - Medium: 50.0
    - Low: 25.0
    """
    crit = max(0, urgency_distribution.get("Critical", 0))
    high = max(0, urgency_distribution.get("High", 0))
    med = max(0, urgency_distribution.get("Medium", 0))
    low = max(0, urgency_distribution.get("Low", 0))

    total = crit + high + med + low
    if total == 0:
        return 50.0  # Neutral baseline if unclassified

    weighted_sum = (crit * 100.0) + (high * 75.0) + (med * 50.0) + (low * 25.0)
    return round(min(100.0, max(0.0, weighted_sum / total)), 2)


def compute_sentiment_score(sentiment_distribution: Dict[str, int]) -> float:
    """
    Computes a customer dissatisfaction / sentiment friction score (0.0 to 100.0).
    Higher scores denote urgent negative sentiment and customer friction:
    - Negative: 90.0
    - Mixed: 60.0
    - Neutral: 40.0
    - Positive: 20.0
    """
    neg = max(0, sentiment_distribution.get("Negative", 0))
    mix = max(0, sentiment_distribution.get("Mixed", 0))
    neu = max(0, sentiment_distribution.get("Neutral", 0))
    pos = max(0, sentiment_distribution.get("Positive", 0))

    total = neg + mix + neu + pos
    if total == 0:
        return 50.0

    weighted_sum = (neg * 90.0) + (mix * 60.0) + (neu * 40.0) + (pos * 20.0)
    return round(min(100.0, max(0.0, weighted_sum / total)), 2)


def compute_usage_impact_score(
    analytics_data: Optional[ProductAnalyticsData],
) -> Optional[float]:
    """
    Computes a normalized usage impact score (0.0 to 100.0) from verified product analytics.
    Returns None if analytics telemetry is unmeasured or unavailable.
    """
    if analytics_data is None or not analytics_data.is_available:
        return None

    components: List[float] = []

    # 1. Engagement score (if provided 0-100)
    if analytics_data.user_engagement_score is not None:
        components.append(min(100.0, max(0.0, analytics_data.user_engagement_score)))

    # 2. Adoption rate (if provided 0-100)
    if analytics_data.adoption_rate is not None:
        components.append(min(100.0, max(0.0, analytics_data.adoption_rate)))

    # 3. Funnel drop-off rate (higher drop-off means higher impact of feature enhancement)
    if analytics_data.drop_off_rate is not None:
        components.append(min(100.0, max(0.0, analytics_data.drop_off_rate)))

    # 4. Active user scale
    if analytics_data.active_users is not None:
        user_score = min(100.0, max(0.0, analytics_data.active_users / 10.0))  # 1000 users = 100
        components.append(user_score)

    if not components:
        return 50.0

    return round(sum(components) / len(components), 2)


def calculate_prioritization_score(
    factor_scores: Dict[str, Optional[float]],
    weights: Optional[FactorWeightConfig] = None,
    thresholds: Optional[ThresholdConfig] = None,
) -> Dict[str, Any]:
    """
    Calculates final composite prioritization score deterministically:
    1. Normalizes factor scores to [0.0, 100.0].
    2. Identifies missing factors and applies the documented missing-data reweighting policy.
    3. Computes exact evidence coverage percentage.
    4. Computes final weighted composite score.
    5. Maps score to PriorityLevel (Critical, High, Medium, Low).
    """
    weight_cfg = weights or FactorWeightConfig()
    threshold_cfg = thresholds or ThresholdConfig()

    raw_weights: Dict[str, float] = {
        FactorName.CUSTOMER_DEMAND.value: weight_cfg.customer_demand,
        FactorName.URGENCY.value: weight_cfg.urgency,
        FactorName.BUSINESS_IMPACT.value: weight_cfg.business_impact,
        FactorName.STRATEGIC_ALIGNMENT.value: weight_cfg.strategic_alignment,
        FactorName.SENTIMENT.value: weight_cfg.sentiment,
        FactorName.USAGE_IMPACT.value: weight_cfg.usage_impact,
    }

    available_factors: Dict[str, float] = {}
    missing_data: List[str] = []

    for factor_key, factor_val in factor_scores.items():
        if factor_val is None:
            missing_data.append(factor_key)
        else:
            # Clamp factor scores to [0.0, 100.0]
            available_factors[factor_key] = min(100.0, max(0.0, float(factor_val)))

    # Check for missing factors among standard weight config
    for factor_key in raw_weights:
        if factor_key not in factor_scores or factor_scores[factor_key] is None:
            if factor_key not in missing_data:
                missing_data.append(factor_key)

    # -------------------------------------------------------------------------
    # Reweighting Policy for Missing Data
    # -------------------------------------------------------------------------
    available_weight_sum = sum(raw_weights[f] for f in available_factors if f in raw_weights)
    if available_weight_sum <= 0:
        # Fallback if no factors available
        return {
            "final_score": 0.0,
            "priority_level": PriorityLevel.LOW,
            "normalized_weights": {},
            "coverage_percentage": 0.0,
            "missing_data": missing_data,
        }

    coverage_percentage = round((available_weight_sum / sum(raw_weights.values())) * 100.0, 2)

    normalized_weights: Dict[str, float] = {}
    weighted_score = 0.0

    for factor_key, factor_score in available_factors.items():
        if factor_key in raw_weights:
            norm_weight = raw_weights[factor_key] / available_weight_sum
            normalized_weights[factor_key] = round(norm_weight, 4)
            weighted_score += factor_score * norm_weight

    final_score = round(min(100.0, max(0.0, weighted_score)), 2)

    # Priority level classification based on configurable thresholds
    if final_score >= threshold_cfg.critical_min:
        priority_level = PriorityLevel.CRITICAL
    elif final_score >= threshold_cfg.high_min:
        priority_level = PriorityLevel.HIGH
    elif final_score >= threshold_cfg.medium_min:
        priority_level = PriorityLevel.MEDIUM
    else:
        priority_level = PriorityLevel.LOW

    return {
        "final_score": final_score,
        "priority_level": priority_level,
        "normalized_weights": normalized_weights,
        "coverage_percentage": coverage_percentage,
        "missing_data": missing_data,
    }


def rank_prioritization_results(
    results: List[PrioritizationResult],
    top_k: Optional[int] = None,
    min_priority: Optional[PriorityLevel] = None,
) -> List[PrioritizationResult]:
    """
    Ranks prioritization results by final_score in descending order.
    Optionally filters by minimum priority tier and caps to top_k items.
    """
    priority_order = {
        PriorityLevel.CRITICAL: 4,
        PriorityLevel.HIGH: 3,
        PriorityLevel.MEDIUM: 2,
        PriorityLevel.LOW: 1,
    }

    filtered = results
    if min_priority is not None:
        min_rank = priority_order.get(min_priority, 1)
        filtered = [r for r in filtered if priority_order.get(r.priority_level, 1) >= min_rank]

    # Sort descending by final_score
    ranked = sorted(filtered, key=lambda r: r.final_score, reverse=True)

    if top_k is not None and top_k > 0:
        return ranked[:top_k]
    return ranked

