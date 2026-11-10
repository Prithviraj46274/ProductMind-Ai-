from datetime import datetime, timezone
from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies import (
    get_audit_log_repository,
    get_current_user,
    get_feedback_batch_repository,
    get_feedback_repository,
    get_feature_repository,
    get_workspace_membership_repository,
    get_workspace_repository,
)
from app.core.enums import FeedbackSourceType, MembershipStatus, PlatformRole, UserRole
from app.main import app
from app.models.auth import User, Workspace, WorkspaceMembership
from app.models.feedback import FeedbackBatch, FeedbackItem, RowErrorSample

client = TestClient(app)
USER_ID = ObjectId("660011223344556677889901")
WORKSPACE_ID = ObjectId("660011223344556677889902")
FEEDBACK_ID = ObjectId("660011223344556677889903")
BATCH_ID = ObjectId("660011223344556677889904")
FEATURE_ID = ObjectId("660011223344556677889905")


def make_feedback(**overrides):
    values = {
        "id": FEEDBACK_ID,
        "workspace_id": WORKSPACE_ID,
        "title": "Slow dashboard",
        "description": "Dashboard loads slowly",
        "source_type": FeedbackSourceType.MANUAL,
        "external_id": "client-feedback-1",
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return FeedbackItem(**values)


@pytest.fixture
def api_state():
    app.dependency_overrides.clear()
    user = User(
        id=USER_ID,
        name="Workspace Owner",
        email="owner@example.test",
        password_hash="mock-password-hash",
        platform_role=PlatformRole.USER,
    )
    workspace = Workspace(
        id=WORKSPACE_ID,
        name="Product Team",
        slug="product-team",
        owner_id=USER_ID,
    )
    workspace_repo = AsyncMock()
    workspace_repo.find_by_id.return_value = workspace
    membership_repo = AsyncMock()
    membership_repo.find_membership.return_value = WorkspaceMembership(
        workspace_id=WORKSPACE_ID,
        user_id=USER_ID,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
    )
    feedback_repo = AsyncMock()
    batch_repo = AsyncMock()
    feature_repo = AsyncMock()
    audit_repo = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_workspace_repository] = lambda: workspace_repo
    app.dependency_overrides[get_workspace_membership_repository] = lambda: membership_repo
    app.dependency_overrides[get_feedback_repository] = lambda: feedback_repo
    app.dependency_overrides[get_feedback_batch_repository] = lambda: batch_repo
    app.dependency_overrides[get_feature_repository] = lambda: feature_repo
    app.dependency_overrides[get_audit_log_repository] = lambda: audit_repo

    yield {
        "user": user,
        "workspace_repo": workspace_repo,
        "membership_repo": membership_repo,
        "feedback_repo": feedback_repo,
        "batch_repo": batch_repo,
        "feature_repo": feature_repo,
        "audit_repo": audit_repo,
    }
    app.dependency_overrides.clear()


def test_create_feedback_maps_linked_feature_and_preserves_ai_owned_defaults(api_state):
    created = make_feedback(
        promoted_feature_id=FEATURE_ID,
        external_id="manual-1",
        processing_status="raw",
    )
    api_state["feature_repo"].find_by_id.return_value = object()
    api_state["feedback_repo"].find_by_external_id.return_value = None
    api_state["feedback_repo"].create.return_value = created

    response = client.post(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}",
        json={
            "title": "Slow dashboard",
            "description": "Dashboard loads slowly",
            "externalId": "manual-1",
            "linkedFeatureId": str(FEATURE_ID),
        },
    )

    assert response.status_code == 201
    assert response.json()["promotedFeatureId"] == str(FEATURE_ID)
    saved_item = api_state["feedback_repo"].create.await_args.args[0]
    assert saved_item.ai_analysis is None
    assert saved_item.ai_predicted_priority is None
    assert saved_item.processing_status.value == "raw"
    api_state["feature_repo"].find_by_id.assert_awaited_once_with(
        str(FEATURE_ID),
        workspace_id=WORKSPACE_ID,
    )


def test_create_feedback_rejects_feature_from_another_workspace(api_state):
    api_state["feature_repo"].find_by_id.return_value = None

    response = client.post(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}",
        json={
            "title": "Slow dashboard",
            "description": "Dashboard loads slowly",
            "externalId": "manual-2",
            "linkedFeatureId": str(FEATURE_ID),
        },
    )

    assert response.status_code == 422
    api_state["feedback_repo"].create.assert_not_awaited()


def test_create_feedback_returns_existing_item_for_idempotent_replay(api_state):
    existing = make_feedback()
    api_state["feedback_repo"].find_by_external_id.return_value = existing

    response = client.post(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}",
        json={
            "title": "Slow dashboard",
            "description": "Dashboard loads slowly",
            "externalId": "client-feedback-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(FEEDBACK_ID)
    api_state["feedback_repo"].create.assert_not_awaited()
    api_state["audit_repo"].create.assert_not_awaited()


def test_create_feedback_rejects_reused_external_id_with_different_content(api_state):
    api_state["feedback_repo"].find_by_external_id.return_value = make_feedback()

    response = client.post(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}",
        json={
            "title": "Slow dashboard",
            "description": "Different feedback content",
            "externalId": "client-feedback-1",
        },
    )

    assert response.status_code == 409
    api_state["feedback_repo"].create.assert_not_awaited()


def test_create_feedback_uses_idempotency_header_when_external_id_is_absent(api_state):
    created = make_feedback(external_id="request-key")
    api_state["feedback_repo"].find_by_external_id.return_value = None
    api_state["feedback_repo"].create.return_value = created

    response = client.post(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}",
        headers={"Idempotency-Key": "request-key"},
        json={"title": "Slow dashboard", "description": "Dashboard loads slowly"},
    )

    assert response.status_code == 201
    saved_item = api_state["feedback_repo"].create.await_args.args[0]
    assert saved_item.external_id == "request-key"


def test_create_feedback_rejects_ai_owned_input_fields(api_state):
    response = client.post(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}",
        json={
            "title": "Slow dashboard",
            "description": "Dashboard loads slowly",
            "externalId": "manual-3",
            "aiAnalysis": {"classification": "forged"},
        },
    )

    assert response.status_code == 422
    api_state["feedback_repo"].create.assert_not_awaited()


def test_batch_import_reports_partial_results_and_persists_bounded_errors(api_state):
    created = make_feedback(
        id=ObjectId("660011223344556677889906"),
        source_type=FeedbackSourceType.JSON,
        external_id="retryable-1",
        batch_id=BATCH_ID,
    )
    batch = FeedbackBatch(
        id=BATCH_ID,
        workspace_id=WORKSPACE_ID,
        uploaded_by=USER_ID,
        source_type=FeedbackSourceType.JSON,
        status="processing",
        total_rows=3,
    )
    api_state["batch_repo"].create.return_value = batch
    api_state["batch_repo"].update.return_value = batch
    api_state["feedback_repo"].find_by_external_id.return_value = None
    api_state["feedback_repo"].create.return_value = created

    response = client.post(
        f"/api/v1/feedback/batch?workspaceId={WORKSPACE_ID}",
        json={
            "items": [
                {"id": "retryable-1", "title": "First item", "description": "Valid content"},
                {"externalId": "invalid-2", "title": "x", "description": "Invalid title"},
                {"title": "Missing key", "description": "Cannot safely retry"},
            ]
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "partial"
    assert body["acceptedRows"] == 1
    assert body["rejectedRows"] == 2
    assert body["duplicateRows"] == 0
    assert [row["status"] for row in body["results"]] == [
        "accepted",
        "rejected",
        "rejected",
    ]
    update_data = api_state["batch_repo"].update.await_args.args[1]
    assert update_data["acceptedRows"] == 1
    assert update_data["rejectedRows"] == 2
    assert len(update_data["errorSummary"]) == 2
    assert all("input" not in error for error in body["results"][1]["errors"])


def test_batch_retry_is_idempotent_for_already_saved_rows(api_state):
    existing = make_feedback(
        source_type=FeedbackSourceType.JSON,
        external_id="retryable-1",
        batch_id=ObjectId("660011223344556677889907"),
        title="First item",
        description="Valid content",
    )
    new_batch = FeedbackBatch(
        id=BATCH_ID,
        workspace_id=WORKSPACE_ID,
        uploaded_by=USER_ID,
        source_type=FeedbackSourceType.JSON,
        status="processing",
        total_rows=1,
    )
    api_state["batch_repo"].create.return_value = new_batch
    api_state["batch_repo"].update.return_value = new_batch
    api_state["feedback_repo"].find_by_external_id.return_value = existing

    response = client.post(
        f"/api/v1/feedback/batch?workspaceId={WORKSPACE_ID}",
        json={
            "items": [
                {"id": "retryable-1", "title": "First item", "description": "Valid content"}
            ]
        },
    )

    assert response.status_code == 201
    assert response.json()["duplicateRows"] == 1
    assert response.json()["results"][0]["status"] == "duplicate"
    api_state["feedback_repo"].create.assert_not_awaited()


def test_list_feedback_passes_filters_and_bounded_pagination(api_state):
    api_state["feedback_repo"].find_page.return_value = ([], 0)

    response = client.get(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}"
        "&page=2&limit=25&category=Performance&sentiment=Negative"
        "&priority=High&linkedFeature=true&sort=priority"
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 2,
        "limit": 25,
        "pages": 0,
    }
    kwargs = api_state["feedback_repo"].find_page.await_args.kwargs
    assert kwargs["page"] == 2
    assert kwargs["limit"] == 25
    assert kwargs["linked"] is True
    assert kwargs["sort"] == "priority"


def test_list_feedback_rejects_pages_over_100_items(api_state):
    response = client.get(
        f"/api/v1/feedback?workspaceId={WORKSPACE_ID}&limit=101"
    )

    assert response.status_code == 422
    api_state["feedback_repo"].find_page.assert_not_awaited()


def test_batch_import_rejects_more_than_500_rows(api_state):
    response = client.post(
        f"/api/v1/feedback/batch?workspaceId={WORKSPACE_ID}",
        json={"items": [{} for _ in range(501)]},
    )

    assert response.status_code == 422
    api_state["batch_repo"].create.assert_not_awaited()


def test_feedback_batch_status_is_workspace_scoped(api_state):
    batch = FeedbackBatch(
        id=BATCH_ID,
        workspace_id=WORKSPACE_ID,
        uploaded_by=USER_ID,
        status="partial",
        total_rows=2,
        accepted_rows=1,
        rejected_rows=1,
        error_summary=[
            RowErrorSample(rowNumber=2, field="title", message="Field is too short")
        ],
    )
    api_state["batch_repo"].find_by_workspace_and_id.return_value = batch

    response = client.get(
        f"/api/v1/feedback/batch/{BATCH_ID}?workspaceId={WORKSPACE_ID}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["errorSummary"][0]["rowNumber"] == 2
    api_state["batch_repo"].find_by_workspace_and_id.assert_awaited_once_with(
        str(BATCH_ID),
        WORKSPACE_ID,
    )


def test_retry_batch_resolves_only_rejected_rows_and_keeps_batch_provenance(api_state):
    batch = FeedbackBatch(
        id=BATCH_ID,
        workspace_id=WORKSPACE_ID,
        uploaded_by=USER_ID,
        source_type=FeedbackSourceType.JSON,
        status="partial",
        total_rows=2,
        accepted_rows=1,
        rejected_rows=1,
        error_summary=[
            RowErrorSample(rowNumber=2, field="title", message="Title was too short")
        ],
    )
    saved_feedback = make_feedback(
        id=ObjectId("660011223344556677889908"),
        source_type=FeedbackSourceType.JSON,
        external_id="retry-2",
        batch_id=BATCH_ID,
        title="Recovered item",
        description="Corrected feedback",
    )
    api_state["batch_repo"].find_by_workspace_and_id.return_value = batch
    api_state["batch_repo"].claim_failed_batch.return_value = batch
    api_state["batch_repo"].update.return_value = batch
    api_state["feedback_repo"].find_by_external_id.return_value = None
    api_state["feedback_repo"].create.return_value = saved_feedback

    response = client.post(
        f"/api/v1/feedback/batch/{BATCH_ID}/retry?workspaceId={WORKSPACE_ID}",
        json={
            "items": [
                {
                    "rowNumber": 2,
                    "item": {
                        "externalId": "retry-2",
                        "title": "Recovered item",
                        "description": "Corrected feedback",
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["acceptedRows"] == 2
    assert response.json()["rejectedRows"] == 0
    saved = api_state["feedback_repo"].create.await_args.args[0]
    assert saved.batch_id == BATCH_ID
    update_data = api_state["batch_repo"].update.await_args.args[1]
    assert update_data["errorSummary"] == []


def test_retry_batch_rejects_rows_not_reported_as_failed(api_state):
    batch = FeedbackBatch(
        id=BATCH_ID,
        workspace_id=WORKSPACE_ID,
        uploaded_by=USER_ID,
        status="partial",
        total_rows=2,
        accepted_rows=1,
        rejected_rows=1,
        error_summary=[
            RowErrorSample(rowNumber=2, field="title", message="Title was too short")
        ],
    )
    api_state["batch_repo"].find_by_workspace_and_id.return_value = batch

    response = client.post(
        f"/api/v1/feedback/batch/{BATCH_ID}/retry?workspaceId={WORKSPACE_ID}",
        json={
            "items": [
                {
                    "rowNumber": 1,
                    "item": {
                        "externalId": "not-failed",
                        "title": "Accepted before",
                        "description": "Do not retry",
                    },
                }
            ]
        },
    )

    assert response.status_code == 422
    api_state["batch_repo"].claim_failed_batch.assert_not_awaited()


def test_list_feedback_requires_workspace_access(api_state):
    api_state["workspace_repo"].find_by_id.return_value = None

    response = client.get(f"/api/v1/feedback?workspaceId={WORKSPACE_ID}")

    assert response.status_code == 404
    api_state["feedback_repo"].find_page.assert_not_awaited()
