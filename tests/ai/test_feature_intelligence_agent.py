"""
ProductMind AI — Feature Intelligence Agent Unit Tests (Step 3)
Tests candidate filtering, deterministic grouping, ID sanitization, demand metrics,
duplicate detection, LLM execution, and capability boundary separation.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.ai.agents.feature_intelligence import (
    FeatureIntelligenceAgent,
    FeatureRequestCandidate,
    FeatureGroupAnalysis,
    FeatureGroupingAgentOutput,
    FeatureGroupResult,
    DuplicateDetectionItem,
    DuplicateDetectionAgentOutput,
    DuplicateType,
    AnalysisStatus,
    filter_eligible_feature_requests,
    calculate_demand_metrics,
    validate_and_sanitize_groups,
    detect_lexical_duplicates,
)
from app.ai.agents.base import AgentExecutionMetadata, AgentExecutionResult
from app.ai.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    service = MagicMock(spec=LLMService)
    service.is_configured = True
    service.provider_name = "groq"
    service.model_name = "qwen/qwen3.8-27b"
    service.provider = MagicMock()
    return service


@pytest.fixture
def sample_candidates():
    return [
        FeatureRequestCandidate(
            feedback_id="661122334455667788990001",
            title="Please add dark mode to the dashboard",
            description="Working late at night is blinding with current white background.",
            category="Feature Request",
            main_theme="UI Customization",
            customer_pain_point="Eye strain during evening usage",
            sentiment="Negative",
            urgency="Medium",
            customer_id="alice@example.com",
            customer_name="Alice Smith",
        ),
        FeatureRequestCandidate(
            feedback_id="661122334455667788990002",
            title="We need a night theme for analytics page",
            description="Our analysts work in low light environments and require dark interface.",
            category="Feature Request",
            main_theme="Themes",
            customer_pain_point="Poor visibility in dim room",
            sentiment="Neutral",
            urgency="Medium",
            customer_id="bob@enterprise.com",
            customer_name="Bob Jones",
        ),
        FeatureRequestCandidate(
            feedback_id="661122334455667788990003",
            title="It would be useful to switch between light and dark themes",
            description="Dashboard should support dark appearance toggle.",
            category="Feature Request",
            main_theme="Themes",
            customer_pain_point="Lack of visual preference settings",
            sentiment="Positive",
            urgency="Low",
            customer_id="alice@example.com",  # Same customer as #1 to test deduplication!
            customer_name="Alice Smith",
        ),
        FeatureRequestCandidate(
            feedback_id="661122334455667788990004",
            title="Add CSV export functionality",
            description="We need to export customer feedback tables as raw CSV files for offline Excel processing.",
            category="Feature Request",
            main_theme="Data Export",
            customer_pain_point="Manual copy-pasting of table rows",
            sentiment="Neutral",
            urgency="High",
            customer_id="carol@corp.com",
            customer_name="Carol Danvers",
        ),
        FeatureRequestCandidate(
            feedback_id="661122334455667788990005",
            title="Allow exporting reports to Excel",
            description="Direct XLSX spreadsheet export formatted with header styles.",
            category="Feature Request",
            main_theme="Data Export",
            customer_pain_point="CSV loses formatting in executive spreadsheets",
            sentiment="Neutral",
            urgency="Medium",
            customer_id="david@analytics.org",
            customer_name="David Miller",
        ),
    ]


# -------------------------------------------------------------------------
# 1. Schema Validation Tests
# -------------------------------------------------------------------------

def test_feature_group_analysis_schema_valid():
    """Verify FeatureGroupAnalysis schema validates correct structured output."""
    analysis = FeatureGroupAnalysis(
        group_name="Dark Mode Theme Support",
        feature_summary="Introduce a toggleable dark mode theme across all dashboard and analytics views.",
        consolidated_description="Multiple customers report severe eye strain when using the dashboard at night. Requires dark palette styling and theme toggle setting.",
        related_feedback_ids=["661122334455667788990001", "661122334455667788990002"],
        common_themes=["UI Customization", "Themes"],
        common_pain_points=["Eye strain in low light environments"],
        evidence=["Working late at night is blinding", "require dark interface"],
        suggested_capability="Theme switcher toggle in user profile settings",
        grouping_confidence=0.92,
        grouping_reason="Both requests describe the identical requirement for a dark visual theme.",
        analysis_status=AnalysisStatus.COMPLETED,
    )
    assert analysis.group_name == "Dark Mode Theme Support"
    assert len(analysis.related_feedback_ids) == 2
    assert analysis.grouping_confidence == 0.92


def test_feature_group_analysis_rejects_empty_ids():
    """Verify FeatureGroupAnalysis rejects empty related_feedback_ids."""
    with pytest.raises(ValidationError):
        FeatureGroupAnalysis(
            group_name="Empty Group",
            feature_summary="Feature summary text here.",
            consolidated_description="Detailed description text here.",
            related_feedback_ids=[],  # Empty
            grouping_confidence=0.8,
            grouping_reason="Reason here",
        )


def test_feature_group_analysis_rejects_invalid_confidence():
    """Verify FeatureGroupAnalysis rejects confidence outside 0.0 - 1.0."""
    with pytest.raises(ValidationError):
        FeatureGroupAnalysis(
            group_name="Invalid Confidence Group",
            feature_summary="Summary of feature.",
            consolidated_description="Consolidated description text.",
            related_feedback_ids=["fid1"],
            grouping_confidence=1.5,  # > 1.0
            grouping_reason="Reason",
        )


# -------------------------------------------------------------------------
# 2. Candidate Filtering Tests
# -------------------------------------------------------------------------

def test_filter_eligible_feature_requests():
    """Verify filter_eligible_feature_requests extracts only feature requests and excludes bugs."""
    raw_items = [
        {
            "id": "1",
            "title": "Please add dark mode",
            "description": "Need night theme",
            "category": "Feature Request",
            "sentiment": "Neutral",
            "aiAnalysis": {"category": "Feature Request", "main_theme": "UI"},
        },
        {
            "id": "2",
            "title": "Application crashes on login",
            "description": "500 Internal server error",
            "category": "Bug",
            "aiAnalysis": {"category": "Bug", "main_theme": "Auth"},
        },
        {
            "id": "3",
            "title": "Dashboard takes 20s to load",
            "description": "Very slow queries",
            "category": "Performance",
            "aiAnalysis": {"category": "Performance"},
        },
        {
            "id": "4",
            "title": "Would love support for CSV export",
            "description": "Export raw table data",
            "category": None,  # Unanalyzed, keyword match fallback
        },
    ]

    candidates = filter_eligible_feature_requests(raw_items)
    cand_ids = [c.feedback_id for c in candidates]

    assert "1" in cand_ids
    assert "4" in cand_ids  # Keyword fallback
    assert "2" not in cand_ids  # Excluded Bug
    assert "3" not in cand_ids  # Excluded Performance


# -------------------------------------------------------------------------
# 3. Deterministic Demand Metrics Tests
# -------------------------------------------------------------------------

def test_calculate_demand_metrics(sample_candidates):
    """Verify calculate_demand_metrics accurately computes counts, unique customers, and distributions in Python."""
    lookup = {c.feedback_id: c for c in sample_candidates}
    # Items 1, 2, 3 have Alice, Bob, Alice (2 unique customers)
    fids = [
        "661122334455667788990001",
        "661122334455667788990002",
        "661122334455667788990003",
    ]

    metrics = calculate_demand_metrics(fids, lookup)

    assert metrics["total_request_count"] == 3
    assert metrics["unique_customer_count"] == 2  # Alice counted once!
    assert metrics["sentiment_distribution"]["Negative"] == 1
    assert metrics["sentiment_distribution"]["Neutral"] == 1
    assert metrics["sentiment_distribution"]["Positive"] == 1
    assert metrics["urgency_distribution"]["Medium"] == 2
    assert metrics["urgency_distribution"]["Low"] == 1


# -------------------------------------------------------------------------
# 4. LLM Output Validation & Sanitization Tests
# -------------------------------------------------------------------------

def test_validate_and_sanitize_groups_rejects_hallucinated_ids(sample_candidates):
    """Verify validate_and_sanitize_groups strips hallucinated IDs and prevents double counting."""
    agent_output = FeatureGroupingAgentOutput(
        groups=[
            FeatureGroupAnalysis(
                group_name="Dark Mode Support",
                feature_summary="Add dark theme across all dashboard views.",
                consolidated_description="Multiple customers requested dark theme support for night work.",
                related_feedback_ids=[
                    "661122334455667788990001",
                    "661122334455667788990002",
                    "FABRICATED_ID_9999999999",  # Hallucinated!
                ],
                common_themes=["UI"],
                common_pain_points=["Eye strain"],
                evidence=["Working late at night is blinding"],
                grouping_confidence=0.9,
                grouping_reason="Same dark mode request.",
            ),
            FeatureGroupAnalysis(
                group_name="Duplicate Assignment Group",
                feature_summary="Another group trying to reuse feedback.",
                consolidated_description="Trying to reassign feedback #1.",
                related_feedback_ids=[
                    "661122334455667788990001",  # Already in group 1!
                ],
                grouping_confidence=0.85,
                grouping_reason="Duplicate claim",
            ),
        ],
        ungrouped_feedback_ids=[],
    )

    sanitized, ungrouped = validate_and_sanitize_groups(
        agent_output=agent_output,
        candidates=sample_candidates,
        confidence_threshold=0.6,
        min_group_size=1,
    )

    # First group should have only the 2 valid IDs (hallucinated stripped)
    assert len(sanitized) == 1
    assert sanitized[0].group_name == "Dark Mode Support"
    assert "FABRICATED_ID_9999999999" not in sanitized[0].related_feedback_ids
    assert len(sanitized[0].related_feedback_ids) == 2

    # Second group had only ID #1 which was already taken, so it got 0 IDs and was dropped
    # Items 3, 4, 5 were not grouped, so they are ungrouped
    assert "661122334455667788990003" in ungrouped
    assert "661122334455667788990004" in ungrouped
    assert "661122334455667788990005" in ungrouped


def test_validate_and_sanitize_groups_confidence_threshold(sample_candidates):
    """Verify groups below confidence_threshold are rejected."""
    agent_output = FeatureGroupingAgentOutput(
        groups=[
            FeatureGroupAnalysis(
                group_name="Low Confidence Group",
                feature_summary="Weak connection summary.",
                consolidated_description="Vague connection between requests.",
                related_feedback_ids=["661122334455667788990004"],
                grouping_confidence=0.45,  # Below 0.6 threshold
                grouping_reason="Weak connection",
            )
        ]
    )

    sanitized, ungrouped = validate_and_sanitize_groups(
        agent_output=agent_output,
        candidates=sample_candidates,
        confidence_threshold=0.6,
    )

    assert len(sanitized) == 0
    assert len(ungrouped) == len(sample_candidates)


# -------------------------------------------------------------------------
# 5. Duplicate Detection Tests
# -------------------------------------------------------------------------

def test_detect_lexical_duplicates():
    """Verify deterministic lexical duplicate detection catches exact and near duplicates."""
    items = [
        FeatureRequestCandidate(
            feedback_id="id1",
            title="Please add dark mode to dashboard",
            description="Dashboard needs a dark theme for nighttime use.",
        ),
        FeatureRequestCandidate(
            feedback_id="id2",
            title="Please add dark mode to dashboard",  # Exact match
            description="Dashboard needs a dark theme for nighttime use.",
        ),
        FeatureRequestCandidate(
            feedback_id="id3",
            title="Please add dark mode to the dashboard",  # Near duplicate
            description="Dashboard really needs a dark theme for nighttime use.",
        ),
        FeatureRequestCandidate(
            feedback_id="id4",
            title="Support CSV export of data tables",  # Completely unrelated
            description="Export data into CSV.",
        ),
    ]

    dupes = detect_lexical_duplicates(items)
    assert len(dupes) >= 2

    exact_matches = [d for d in dupes if d.duplicate_type == DuplicateType.EXACT_DUPLICATE]
    assert len(exact_matches) == 1
    assert exact_matches[0].feedback_id == "id1"
    assert exact_matches[0].matched_feedback_id == "id2"
    assert exact_matches[0].confidence == 1.0


# -------------------------------------------------------------------------
# 6. Agent Execution with Mocked LLM Tests
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_execute_mocked(mock_llm_service, sample_candidates):
    """Verify FeatureIntelligenceAgent executes with mocked LLM and returns structured result."""
    mock_output = FeatureGroupingAgentOutput(
        groups=[
            FeatureGroupAnalysis(
                group_name="Dark Mode Support",
                feature_summary="Add toggleable dark mode across all analytics dashboards.",
                consolidated_description="Customers require a dark color palette to reduce eye fatigue during night work.",
                related_feedback_ids=[
                    "661122334455667788990001",
                    "661122334455667788990002",
                    "661122334455667788990003",
                ],
                common_themes=["UI Customization", "Themes"],
                common_pain_points=["Eye strain in dark environments"],
                evidence=["Working late at night is blinding", "require dark interface"],
                suggested_capability="Dark theme toggle switch",
                grouping_confidence=0.95,
                grouping_reason="All three items describe dark appearance for dashboard.",
            )
        ],
        ungrouped_feedback_ids=[
            "661122334455667788990004",
            "661122334455667788990005",
        ],
        overall_reasoning="Grouped dark mode requests together; kept CSV and Excel export separate as distinct export capabilities.",
    )

    mock_llm_service.provider.ainvoke_structured = AsyncMock(return_value=mock_output)

    agent = FeatureIntelligenceAgent(llm_service=mock_llm_service)
    result = await agent.execute({"candidates": sample_candidates})

    assert isinstance(result, AgentExecutionResult)
    assert len(result.data.groups) == 1
    assert result.data.groups[0].group_name == "Dark Mode Support"
    assert len(result.data.groups[0].related_feedback_ids) == 3
    assert len(result.data.ungrouped_feedback_ids) == 2
    assert result.metadata.agent_id == "feature_intelligence_agent"
    assert result.metadata.provider == "groq"
    assert result.metadata.model == "qwen/qwen3.8-27b"


@pytest.mark.asyncio
async def test_agent_detect_duplicates_mocked(mock_llm_service, sample_candidates):
    """Verify agent detect_duplicates produces structured duplicate evaluations."""
    mock_output = DuplicateDetectionAgentOutput(
        duplicates=[
            DuplicateDetectionItem(
                feedback_id="661122334455667788990001",
                matched_feedback_id="661122334455667788990002",
                duplicate_type=DuplicateType.SEMANTIC_EQUIVALENT,
                similarity_explanation="Dark mode and night theme represent the identical capability.",
                confidence=0.94,
                recommendation="Merge into consolidated Dark Mode feature group.",
            ),
            DuplicateDetectionItem(
                feedback_id="661122334455667788990004",
                matched_feedback_id="661122334455667788990005",
                duplicate_type=DuplicateType.RELATED_DISTINCT,
                similarity_explanation="CSV and Excel both deal with export but require distinct format generators.",
                confidence=0.88,
                recommendation="Keep as separate feature items on the roadmap.",
            ),
        ],
        summary="Found 1 semantic duplicate pair and 1 related distinct pair.",
    )

    mock_llm_service.provider.ainvoke_structured = AsyncMock(return_value=mock_output)

    agent = FeatureIntelligenceAgent(llm_service=mock_llm_service)
    result = await agent.detect_duplicates(sample_candidates)

    assert isinstance(result, AgentExecutionResult)
    assert len(result.data.duplicates) == 2
    assert result.data.duplicates[0].duplicate_type == DuplicateType.SEMANTIC_EQUIVALENT
    assert result.data.duplicates[1].duplicate_type == DuplicateType.RELATED_DISTINCT

