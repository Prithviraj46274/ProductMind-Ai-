"""
ProductMind AI — Deterministic Feature Grouping & Aggregation Engine
Implements deterministic candidate filtering, LLM output validation, ID sanitization,
demand metrics calculation in Python, and lexical duplicate detection.
"""

from collections import Counter
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from app.ai.agents.feature_intelligence.schemas import (
    FeatureRequestCandidate,
    FeatureGroupAnalysis,
    FeatureGroupingAgentOutput,
    DuplicateDetectionItem,
    DuplicateType,
)
from app.core.enums import FeedbackCategory


FEATURE_REQUEST_SYNONYMS = {
    "feature request",
    "feature requests",
    "feature",
    "feature_request",
    "enhancement",
    "request",
    "feedbackcategory.feature_requests",
    "feedbackclassificationcategory.feature_request",
}


FEATURE_REQUEST_KEYWORDS = [
    "please add",
    "would love",
    "would like",
    "need ability to",
    "should allow",
    "feature request",
    "can we have",
    "support for",
    "add support",
    "integrate with",
    "missing ability",
    "allow us to",
    "ability to",
]


def filter_eligible_feature_requests(
    feedback_items: List[Any],
) -> List[FeatureRequestCandidate]:
    """
    Filters raw or analyzed feedback records to extract eligible feature requests.
    Prioritizes existing Feedback Intelligence analysis results, with an explicit
    safe fallback for category field or keyword-based classification.
    """
    candidates: List[FeatureRequestCandidate] = []

    for item in feedback_items:
        # Determine dict representation or model fields
        if hasattr(item, "model_dump"):
            data = item.model_dump()
            raw_id = str(item.id if hasattr(item, "id") and item.id else data.get("id") or data.get("_id") or "")
        elif isinstance(item, dict):
            data = item
            raw_id = str(data.get("id") or data.get("_id") or "")
        else:
            continue

        if not raw_id:
            continue

        title = str(data.get("title") or "").strip()
        description = str(data.get("description") or "").strip()
        full_text = f"{title} {description}".lower()

        # Check existing AI analysis first
        ai_analysis = data.get("ai_analysis") or data.get("aiAnalysis") or {}
        ai_cat_raw = ai_analysis.get("category")
        ai_category = str(getattr(ai_cat_raw, "value", ai_cat_raw) or "").strip().lower()

        is_feature_request = False

        if ai_category in FEATURE_REQUEST_SYNONYMS or "feature" in ai_category:
            is_feature_request = True
        elif not ai_category:
            # Fallback policy: inspect existing category field
            cat_raw = data.get("category")
            category_val = str(getattr(cat_raw, "value", cat_raw) or "").strip().lower()
            if category_val in FEATURE_REQUEST_SYNONYMS or "feature" in category_val:
                is_feature_request = True
            elif any(kw in full_text for kw in FEATURE_REQUEST_KEYWORDS):
                is_feature_request = True


        if not is_feature_request:
            continue

        # Extract enriched fields from ai_analysis if available
        main_theme = ai_analysis.get("main_theme") or (
            data.get("ai_themes", [None])[0] if data.get("ai_themes") else None
        )
        customer_pain_point = ai_analysis.get("customer_pain_point") or ""
        sentiment = (
            ai_analysis.get("sentiment")
            or data.get("sentiment")
            or "Neutral"
        )
        urgency = (
            ai_analysis.get("urgency")
            or data.get("ai_predicted_priority")
            or data.get("source_priority")
            or "Medium"
        )

        customer_id = (
            data.get("customer_email")
            or data.get("customerEmail")
            or data.get("customer_name")
            or data.get("customerName")
            or data.get("company_name")
            or data.get("companyName")
            or f"cust_{raw_id}"
        )

        candidates.append(
            FeatureRequestCandidate(
                feedback_id=raw_id,
                title=title or "Untitled Feature Request",
                description=description,
                category="Feature Request",
                main_theme=str(main_theme) if main_theme else None,
                customer_pain_point=str(customer_pain_point) if customer_pain_point else None,
                sentiment=str(sentiment) if sentiment else "Neutral",
                urgency=str(urgency) if urgency else "Medium",
                customer_id=str(customer_id) if customer_id else None,
                customer_name=data.get("customer_name") or data.get("customerName"),
                company_name=data.get("company_name") or data.get("companyName"),
            )
        )

    return candidates


def format_candidates_for_prompt(candidates: List[FeatureRequestCandidate]) -> str:
    """Formats normalized feature request candidates into structured prompt text."""
    blocks = []
    for idx, c in enumerate(candidates, 1):
        context_parts = []
        if c.customer_name:
            context_parts.append(f"Customer: {c.customer_name}")
        if c.company_name:
            context_parts.append(f"Company: {c.company_name}")
        cust_str = ", ".join(context_parts) if context_parts else "Anonymous Customer"

        lines = [
            f"--- Candidate #{idx} ---",
            f"Feedback ID: {c.feedback_id}",
            f"Title: {c.title}",
        ]
        if c.description:
            lines.append(f"Description: {c.description}")
        if c.main_theme:
            lines.append(f"Theme: {c.main_theme}")
        if c.customer_pain_point:
            lines.append(f"Pain Point: {c.customer_pain_point}")
        lines.append(f"Sentiment: {c.sentiment or 'Neutral'} | Urgency: {c.urgency or 'Medium'}")
        lines.append(f"Customer: {cust_str}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def calculate_demand_metrics(
    related_feedback_ids: List[str],
    candidate_lookup: Dict[str, FeatureRequestCandidate],
) -> Dict[str, Any]:
    """
    Computes demand totals, customer deduplication, and sentiment/urgency distributions
    strictly in deterministic Python. Avoids double-counting and LLM fabrication.
    """
    total_requests = len(related_feedback_ids)
    unique_customers: Set[str] = set()

    sentiment_counter: Counter = Counter()
    urgency_counter: Counter = Counter()

    for fid in related_feedback_ids:
        candidate = candidate_lookup.get(fid)
        if not candidate:
            continue

        # Track unique customer identifier
        cust_key = candidate.customer_id or candidate.customer_name or candidate.feedback_id
        unique_customers.add(str(cust_key).strip().lower())

        # Normalize sentiment
        sent = (candidate.sentiment or "Neutral").capitalize()
        if sent in {"Positive", "Neutral", "Negative", "Mixed"}:
            sentiment_counter[sent] += 1
        else:
            sentiment_counter["Neutral"] += 1

        # Normalize urgency
        urg = (candidate.urgency or "Medium").capitalize()
        if urg in {"Critical", "High", "Medium", "Low"}:
            urgency_counter[urg] += 1
        else:
            urgency_counter["Medium"] += 1

    return {
        "total_request_count": total_requests,
        "unique_customer_count": max(1, len(unique_customers)),
        "sentiment_distribution": {
            "Positive": sentiment_counter["Positive"],
            "Neutral": sentiment_counter["Neutral"],
            "Negative": sentiment_counter["Negative"],
            "Mixed": sentiment_counter["Mixed"],
        },
        "urgency_distribution": {
            "Critical": urgency_counter["Critical"],
            "High": urgency_counter["High"],
            "Medium": urgency_counter["Medium"],
            "Low": urgency_counter["Low"],
        },
    }


def validate_and_sanitize_groups(
    agent_output: FeatureGroupingAgentOutput,
    candidates: List[FeatureRequestCandidate],
    confidence_threshold: float = 0.6,
    min_group_size: int = 1,
) -> Tuple[List[FeatureGroupAnalysis], List[str]]:
    """
    Validates LLM grouping output against actual input candidates:
    1. Rejects feedback IDs not present in input candidates (hallucination guard).
    2. Enforces unique assignment (no feedback item assigned to multiple groups).
    3. Enforces minimum confidence threshold.
    4. Enforces minimum group size.
    5. Returns sanitized groups and list of ungrouped feedback IDs.
    """
    valid_ids: Set[str] = {c.feedback_id for c in candidates}
    candidate_lookup: Dict[str, FeatureRequestCandidate] = {c.feedback_id: c for c in candidates}

    # Index lookup for candidate positional references (e.g. "Candidate #1", "#1", "1")
    index_lookup: Dict[str, str] = {}
    for idx, c in enumerate(candidates, 1):
        index_lookup[str(idx)] = c.feedback_id
        index_lookup[f"#{idx}"] = c.feedback_id
        index_lookup[f"candidate #{idx}".lower()] = c.feedback_id
        index_lookup[f"candidate {idx}".lower()] = c.feedback_id

    sanitized_groups: List[FeatureGroupAnalysis] = []
    assigned_ids: Set[str] = set()

    for group in agent_output.groups:
        # Confidence check
        if group.grouping_confidence < confidence_threshold:
            continue

        # Filter to valid, unassigned feedback IDs belonging strictly to input candidates
        clean_fids: List[str] = []
        for fid in group.related_feedback_ids:
            clean_id = str(fid).strip()
            resolved_id = clean_id if clean_id in valid_ids else index_lookup.get(clean_id.lower())
            if resolved_id and resolved_id in valid_ids and resolved_id not in assigned_ids:
                clean_fids.append(resolved_id)

        # Check minimum group size requirement
        if len(clean_fids) < min_group_size:
            continue

        # Mark IDs as assigned
        for fid in clean_fids:
            assigned_ids.add(fid)

        # Filter evidence to text actually found in group candidates
        combined_text = " ".join(
            f"{candidate_lookup[fid].title} {candidate_lookup[fid].description}".lower()
            for fid in clean_fids
            if fid in candidate_lookup
        )
        valid_evidence = []
        for ev in group.evidence:
            ev_clean = str(ev).strip()
            if not ev_clean:
                continue
            # If quote is present in combined text or reasonably short excerpt
            if ev_clean.lower() in combined_text or len(ev_clean) < 150:
                valid_evidence.append(ev_clean)

        sanitized_group = FeatureGroupAnalysis(
            group_name=group.group_name.strip(),
            feature_summary=group.feature_summary.strip(),
            consolidated_description=group.consolidated_description.strip(),
            related_feedback_ids=clean_fids,
            common_themes=[t.strip() for t in group.common_themes if t.strip()],
            common_pain_points=[p.strip() for p in group.common_pain_points if p.strip()],
            evidence=valid_evidence,
            suggested_capability=group.suggested_capability,
            grouping_confidence=round(group.grouping_confidence, 2),
            grouping_reason=group.grouping_reason.strip(),
            analysis_status=group.analysis_status,
        )
        sanitized_groups.append(sanitized_group)

    # Compute unassigned / ungrouped feedback IDs
    ungrouped_ids = [cid for cid in sorted(valid_ids) if cid not in assigned_ids]

    return sanitized_groups, ungrouped_ids


# -------------------------------------------------------------------------
# Deterministic Lexical Duplicate Detection
# -------------------------------------------------------------------------

def _tokenize(text: str) -> Set[str]:
    """Extracts alphanumeric words from text."""
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
    return set(words)


def _jaccard_similarity(s1: Set[str], s2: Set[str]) -> float:
    """Calculates Jaccard token similarity between two word sets."""
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


def detect_lexical_duplicates(
    candidates: List[FeatureRequestCandidate],
) -> List[DuplicateDetectionItem]:
    """
    Evaluates exact and near lexical duplicates among candidates deterministically.
    Pairs with Jaccard overlap >= 0.85 are flagged as near_duplicate; exact matches as exact_duplicate.
    """
    results: List[DuplicateDetectionItem] = []
    n = len(candidates)

    for i in range(n):
        c1 = candidates[i]
        text1 = f"{c1.title} {c1.description}".strip()
        tokens1 = _tokenize(text1)

        for j in range(i + 1, n):
            c2 = candidates[j]
            text2 = f"{c2.title} {c2.description}".strip()
            tokens2 = _tokenize(text2)

            if text1.lower() == text2.lower():
                results.append(
                    DuplicateDetectionItem(
                        feedback_id=c1.feedback_id,
                        matched_feedback_id=c2.feedback_id,
                        duplicate_type=DuplicateType.EXACT_DUPLICATE,
                        similarity_explanation="Exact verbatim textual match across title and description.",
                        confidence=1.0,
                        recommendation="Merge into single feature request representation; deduplicate customer count.",
                    )
                )
                continue

            sim = _jaccard_similarity(tokens1, tokens2)
            if sim >= 0.85:
                results.append(
                    DuplicateDetectionItem(
                        feedback_id=c1.feedback_id,
                        matched_feedback_id=c2.feedback_id,
                        duplicate_type=DuplicateType.NEAR_DUPLICATE,
                        similarity_explanation=f"High lexical and token similarity ({round(sim * 100, 1)}% token overlap).",
                        confidence=round(sim, 2),
                        recommendation="Merge into single feature group; distinct phrasing expressing identical request.",
                    )
                )

    return results

