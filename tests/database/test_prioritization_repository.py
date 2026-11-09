"""
ProductMind AI — Prioritization Scenario Repository Unit Tests
Tests CRUD operations, backward-compatible AI fields, workspace isolation,
and score ranking on PrioritizationScenarioRepository.
"""

from datetime import datetime, timezone
from bson import ObjectId
import pytest

from app.models.planning import PrioritizationScenario
from app.repositories import PrioritizationScenarioRepository


@pytest.mark.asyncio
async def test_prioritization_crud_lifecycle(async_db):
    """Verify PrioritizationScenario creation, retrieval, updating, and cleanup."""
    repo = PrioritizationScenarioRepository(async_db)
    test_ws_id = ObjectId()
    test_fg_id = ObjectId()

    scenario = PrioritizationScenario(
        workspace_id=test_ws_id,
        name="Automated Export Integration",
        description="Comprehensive export functionality for analyst workflows.",
        feature_group_id=test_fg_id,
        final_score=82.5,
        priority_level="Critical",
        factor_scores={
            "customer_demand": 80.0,
            "urgency": 75.0,
            "business_impact": 85.0,
            "strategic_alignment": 90.0,
            "sentiment": 90.0,
        },
        factor_weights={
            "customer_demand": 0.2778,
            "urgency": 0.2222,
            "business_impact": 0.2222,
            "strategic_alignment": 0.1667,
            "sentiment": 0.1111,
        },
        coverage_percentage=90.0,
        explanation="High customer demand and urgency drive critical priority.",
        implementation_benefits=["Automates 3 hours of manual reporting", "Improves data pipeline agility"],
        delay_risks=["Analysts churn to competing platforms"],
        supporting_evidence=["Need automated CSV export daily"],
        missing_data=["usage_impact"],
        recommendation="Immediate sprint priority.",
        ai_metadata={"agent_id": "prioritization_agent", "model": "qwen/qwen3.8-27b"},
        version=1,
        is_active=True,
    )

    created = await repo.create(scenario)
    try:
        assert created.id is not None
        assert created.name == "Automated Export Integration"
        assert created.final_score == 82.5
        assert created.priority_level == "Critical"
        assert created.coverage_percentage == 90.0
        assert len(created.missing_data) == 1
        assert created.version == 1

        # 1. Find by ID
        fetched = await repo.find_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.feature_group_id == test_fg_id

        # 2. Update via $set dict (BaseRepository.update signature)
        updated = await repo.update(
            entity_id=created.id,
            update_data={"finalScore": 88.0, "version": 2},
        )
        assert updated is not None
        assert updated.final_score == 88.0
        assert updated.version == 2

    finally:
        if created and created.id:
            await repo.delete(created.id)


@pytest.mark.asyncio
async def test_find_by_workspace_and_feature_group(async_db):
    """Verify lookup by workspace ID and feature group ID."""
    repo = PrioritizationScenarioRepository(async_db)
    test_ws_id = ObjectId()
    test_fg_id = ObjectId()

    scenario = PrioritizationScenario(
        workspace_id=test_ws_id,
        name="Dark Mode Support",
        feature_group_id=test_fg_id,
        final_score=76.0,
        priority_level="High",
        is_active=True,
    )

    created = await repo.create(scenario)
    try:
        found = await repo.find_by_workspace_and_feature_group(
            workspace_id=test_ws_id,
            feature_group_id=test_fg_id,
        )
        assert found is not None
        assert found.id == created.id
        assert found.final_score == 76.0

        # Mismatched feature group returns None
        not_found = await repo.find_by_workspace_and_feature_group(
            workspace_id=test_ws_id,
            feature_group_id=ObjectId(),
        )
        assert not_found is None

    finally:
        if created and created.id:
            await repo.delete(created.id)


@pytest.mark.asyncio
async def test_find_ranked_by_score_and_tenant_isolation(async_db):
    """Verify descending score ordering and strict tenant isolation."""
    repo = PrioritizationScenarioRepository(async_db)
    ws_a = ObjectId()
    ws_b = ObjectId()

    scenarios_a = [
        PrioritizationScenario(workspace_id=ws_a, name="Feature Low", final_score=35.0, priority_level="Low", is_active=True),
        PrioritizationScenario(workspace_id=ws_a, name="Feature Critical", final_score=92.0, priority_level="Critical", is_active=True),
        PrioritizationScenario(workspace_id=ws_a, name="Feature High", final_score=72.0, priority_level="High", is_active=True),
    ]

    scenario_b = PrioritizationScenario(
        workspace_id=ws_b,
        name="Workspace B Feature",
        final_score=99.0,
        priority_level="Critical",
        is_active=True,
    )

    created_ids = []
    try:
        for s in scenarios_a:
            c = await repo.create(s)
            created_ids.append(c.id)

        cb = await repo.create(scenario_b)
        created_ids.append(cb.id)

        # Ranked query for Workspace A
        ranked_a = await repo.find_ranked_by_score(workspace_id=ws_a)
        assert len(ranked_a) == 3
        assert [s.name for s in ranked_a] == ["Feature Critical", "Feature High", "Feature Low"]
        assert [s.final_score for s in ranked_a] == [92.0, 72.0, 35.0]

        # Tenant isolation: Workspace A query does not contain Workspace B feature
        assert not any(s.workspace_id == ws_b for s in ranked_a)

    finally:
        for cid in created_ids:
            await repo.delete(cid)

