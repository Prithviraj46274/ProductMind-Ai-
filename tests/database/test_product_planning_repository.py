"""
ProductMind AI — Product Planning / PRD Repository Unit Tests
Tests CRUD operations, backward-compatible AI fields, feature group linkage,
status filtering, and tenant isolation on PRDRepository.
"""

from datetime import datetime, timezone
from bson import ObjectId
import pytest

from app.models.planning import PRD, PRDSections
from app.core.enums import PRDStatus
from app.repositories import PRDRepository


@pytest.mark.asyncio
async def test_prd_crud_lifecycle(async_db):
    """Verify PRD creation with structured planning fields, retrieval, update, and cleanup."""
    repo = PRDRepository(async_db)
    test_ws_id = ObjectId()
    test_fg_id = ObjectId()
    test_p_id = ObjectId()

    prd = PRD(
        workspace_id=test_ws_id,
        feature_group_id=test_fg_id,
        prioritization_scenario_id=test_p_id,
        title="Streaming CSV Engine",
        version="1.0.0",
        status=PRDStatus.PENDING_REVIEW,
        author="PM Lead",
        sections=PRDSections(
            overview="Automated CSV report streaming",
            problem_statement="Manual copy-pasting takes 2 hours",
            proposed_solution="Async download endpoint",
        ),
        ai_generated=True,
        structured_prd={
            "title": "Streaming CSV Engine",
            "executive_summary": "Automated CSV report streaming",
            "problem_statement": "Manual copy-pasting takes 2 hours",
            "proposed_solution": "Async download endpoint",
            "customer_pain_points": ["Manual entry"],
        },
        user_stories=[
            {
                "story_id": "US-001",
                "title": "Download CSV",
                "description": "As an analyst, I want to download CSV",
                "persona": "Analyst",
                "business_value": "Saves 2 hours",
                "priority": "Critical",
                "acceptance_criteria": [
                    {
                        "criterion_id": "AC-001",
                        "description": "Given table, When click export, Then downloads",
                        "scenario_type": "positive",
                        "testable": True,
                    }
                ],
            }
        ],
        technical_requirements=[
            {
                "title": "Streaming route",
                "description": "Stream memory",
                "category": "api",
                "rationale": "Prevents OOM",
                "confidence": 0.9,
                "requires_engineering_review": True,
            }
        ],
        success_metrics=[
            {
                "metric_name": "Active Export Users",
                "description": "Users exporting weekly",
                "measurement_method": "Event count",
                "baseline": None,
                "requires_confirmation": True,
            }
        ],
        risk_analysis=[
            {
                "description": "Memory spike",
                "category": "technical",
                "impact": "High",
                "likelihood": "Medium",
                "mitigation": "Worker queues",
                "requires_human_review": True,
            }
        ],
        roadmap_recommendations=[
            {
                "phase_name": "Phase 1",
                "objective": "Core endpoint",
                "tasks": ["Build API"],
                "deliverables": ["API v1"],
                "suggested_sequencing": 1,
            }
        ],
        supporting_evidence=["We need CSV export to renew our contract."],
        review_notes=None,
    )

    created = await repo.create(prd)
    try:
        assert created.id is not None
        assert created.title == "Streaming CSV Engine"
        assert created.status == PRDStatus.PENDING_REVIEW
        assert created.feature_group_id == test_fg_id
        assert created.prioritization_scenario_id == test_p_id
        assert len(created.user_stories) == 1
        assert len(created.technical_requirements) == 1
        assert created.technical_requirements[0]["requires_engineering_review"] is True
        assert created.success_metrics[0]["baseline"] is None

        # 1. Find by ID
        fetched = await repo.find_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "Streaming CSV Engine"

        # 2. Update status to Approved
        updated = await repo.update(
            entity_id=created.id,
            update_data={
                "status": PRDStatus.APPROVED.value,
                "reviewNotes": "Approved by Head of Product",
            },
            workspace_id=test_ws_id,
        )
        assert updated is not None
        assert updated.status == PRDStatus.APPROVED
        assert updated.review_notes == "Approved by Head of Product"

    finally:
        if created and created.id:
            await repo.delete(created.id, workspace_id=test_ws_id)


@pytest.mark.asyncio
async def test_find_by_feature_group(async_db):
    """Verify lookup by workspace ID and feature group ID."""
    repo = PRDRepository(async_db)
    test_ws_id = ObjectId()
    test_fg_id = ObjectId()

    prd = PRD(
        workspace_id=test_ws_id,
        feature_group_id=test_fg_id,
        title="Custom Webhooks PRD",
        status=PRDStatus.DRAFT,
        ai_generated=True,
    )

    created = await repo.create(prd)
    try:
        found = await repo.find_by_feature_group(
            workspace_id=test_ws_id,
            feature_group_id=test_fg_id,
        )
        assert found is not None
        assert found.id == created.id
        assert found.title == "Custom Webhooks PRD"

        # Mismatched feature group returns None
        not_found = await repo.find_by_feature_group(
            workspace_id=test_ws_id,
            feature_group_id=ObjectId(),
        )
        assert not_found is None

    finally:
        if created and created.id:
            await repo.delete(created.id, workspace_id=test_ws_id)


@pytest.mark.asyncio
async def test_find_by_workspace_and_filters_and_tenant_isolation(async_db):
    """Verify filtering by review status and strict multi-tenant isolation."""
    repo = PRDRepository(async_db)
    ws_a = ObjectId()
    ws_b = ObjectId()

    prds_a = [
        PRD(workspace_id=ws_a, title="Plan Draft", status=PRDStatus.DRAFT),
        PRD(workspace_id=ws_a, title="Plan Approved", status=PRDStatus.APPROVED),
        PRD(workspace_id=ws_a, title="Plan Pending", status=PRDStatus.PENDING_REVIEW),
    ]

    prd_b = PRD(
        workspace_id=ws_b,
        title="Workspace B Secret Feature",
        status=PRDStatus.APPROVED,
    )

    created_ids = []
    try:
        for p in prds_a:
            c = await repo.create(p)
            created_ids.append((c.id, ws_a))

        cb = await repo.create(prd_b)
        created_ids.append((cb.id, ws_b))

        # 1. Filter all Workspace A plans
        all_a = await repo.find_by_workspace_and_filters(workspace_id=ws_a)
        assert len(all_a) == 3

        # 2. Filter by status == Approved
        approved_a = await repo.find_by_workspace_and_filters(
            workspace_id=ws_a,
            status=PRDStatus.APPROVED.value,
        )
        assert len(approved_a) == 1
        assert approved_a[0].title == "Plan Approved"

        # 3. Tenant isolation: Workspace B plan is never returned in Workspace A queries
        assert not any(p.workspace_id == ws_b for p in all_a)

    finally:
        for cid, wid in created_ids:
            await repo.delete(cid, workspace_id=wid)

