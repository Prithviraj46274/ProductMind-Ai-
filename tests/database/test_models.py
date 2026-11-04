"""
ProductMind AI — Python Data Model & Validation Tests
"""

import pytest
from datetime import datetime
from bson import ObjectId

from app.database.objectid import PyObjectId, to_object_id
from app.core.enums import (
    calculate_priority_score,
    get_priority_tier,
    PriorityTier,
    FeatureStatus,
    PRDStatus,
    UserRole,
    WorkspacePlan,
)
from app.models.auth import User, Workspace, WorkspaceSettings
from app.models.planning import Feature, Release, ReleaseChecklistItem, PRD, RoadmapItem
from app.models.intelligence import FeatureGroup, SentimentDistribution


def test_priority_score_formula_exactness():
    # Test neutral midpoints
    score = calculate_priority_score(5, 5, 5, 5)
    assert score == 5.0
    assert get_priority_tier(score) == PriorityTier.MEDIUM

    # Test high critical score
    score_high = calculate_priority_score(10, 9, 8, 9)
    # (0.35 * 10) + (0.30 * 9) + (0.20 * 8) + (0.15 * 9) = 3.5 + 2.7 + 1.6 + 1.35 = 9.15
    assert score_high == 9.15
    assert get_priority_tier(score_high) == PriorityTier.CRITICAL

    # Test boundary conditions
    assert get_priority_tier(8.5) == PriorityTier.CRITICAL
    assert get_priority_tier(8.49) == PriorityTier.HIGH
    assert get_priority_tier(7.0) == PriorityTier.HIGH
    assert get_priority_tier(6.99) == PriorityTier.MEDIUM
    assert get_priority_tier(5.0) == PriorityTier.MEDIUM
    assert get_priority_tier(4.99) == PriorityTier.LOW


def test_py_object_id_validation():
    valid_hex = "6ae0b2f08eb7ad472c041b96"
    oid = to_object_id(valid_hex)
    assert isinstance(oid, ObjectId)
    assert str(oid) == valid_hex

    existing_oid = ObjectId()
    assert to_object_id(existing_oid) == existing_oid

    with pytest.raises(ValueError):
        to_object_id("invalid-hex-string")


def test_user_model_serialization():
    u = User(
        name="Alex Rivera",
        email="Alex.Rivera@ProductMind.AI  ",
        passwordHash="$2a$10$abcdefghijklmnopqrstuvwxyz",
    )
    assert u.email == "alex.rivera@productmind.ai"
    assert u.name == "Alex Rivera"

    doc = u.to_mongo()
    assert doc["email"] == "alex.rivera@productmind.ai"
    assert "passwordHash" in doc
    assert doc["platformRole"] == "user"


def test_release_readiness_and_gates():
    ws_id = ObjectId()
    # Empty checklist -> readiness 0%, gated True
    rel = Release(
        workspaceId=ws_id,
        name="Sprint 2026",
        version="v1.0.0",
        plannedDate="2026-11-01",
        checklist=[],
    )
    assert rel.readiness_percent == 0
    assert rel.is_gated is True

    # Checklist with completed items
    rel.checklist = [
        ReleaseChecklistItem(title="Gate 1", completed=True, required=True),
        ReleaseChecklistItem(title="Gate 2", completed=False, required=False),
    ]
    assert rel.readiness_percent == 50
    assert rel.is_gated is False

    # Required item incomplete -> gated True
    rel.checklist.append(ReleaseChecklistItem(title="Gate 3", completed=False, required=True))
    assert rel.is_gated is True

