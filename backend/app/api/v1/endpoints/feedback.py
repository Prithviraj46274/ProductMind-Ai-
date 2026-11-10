"""
Workspace-scoped feedback ingestion and retrieval endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from app.api.dependencies import (
    get_audit_log_repository,
    get_current_user,
    get_feedback_batch_repository,
    get_feedback_repository,
    get_feature_repository,
    get_workspace_membership_repository,
    get_workspace_repository,
)
from app.api.workspace_access import load_accessible_workspace
from app.core.enums import (
    AuditAction,
    AuditEntityType,
    FeedbackCategory,
    FeedbackPriority,
    FeedbackSentiment,
    FeedbackSourceType,
)
from app.models.audit import AuditLog
from app.models.auth import User, Workspace
from app.models.feedback import FeedbackBatch, FeedbackItem, RowErrorSample
from app.repositories import (
    AuditLogRepository,
    DuplicateEntityError,
    FeedbackBatchRepository,
    FeedbackRepository,
    FeatureRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas.feedback import (
    FeedbackBatchIngestResponse,
    FeedbackBatchRequest,
    FeedbackBatchRowResult,
    FeedbackBatchRetryRequest,
    FeedbackBatchStatusResponse,
    FeedbackItemCreate,
    FeedbackItemResponse,
    FeedbackListResponse,
    FeedbackRowError,
)

logger = logging.getLogger("productmind.api.feedback")

router = APIRouter(prefix="/feedback", tags=["Feedback"])


async def _load_workspace(
    workspace_id: str,
    user: User,
    workspace_repo: WorkspaceRepository,
    membership_repo: WorkspaceMembershipRepository,
) -> Workspace:
    workspace, _, _, _ = await load_accessible_workspace(
        workspace_id,
        user,
        workspace_repo,
        membership_repo,
    )
    return workspace


def _feedback_response(item: FeedbackItem) -> FeedbackItemResponse:
    return FeedbackItemResponse(
        id=str(item.id),
        workspace_id=str(item.workspace_id),
        title=item.title,
        description=item.description,
        source_type=item.source_type,
        source_url=item.source_url,
        external_id=item.external_id,
        customer_name=item.customer_name,
        customer_email=item.customer_email,
        company_name=item.company_name,
        category=item.category,
        sentiment=item.sentiment,
        source_priority=item.source_priority,
        ai_predicted_priority=item.ai_predicted_priority,
        tags=item.tags,
        batch_id=str(item.batch_id) if item.batch_id else None,
        feedback_date=item.feedback_date,
        feature_group_id=str(item.feature_group_id) if item.feature_group_id else None,
        promoted_feature_id=str(item.promoted_feature_id) if item.promoted_feature_id else None,
        processing_status=item.processing_status,
        created_at=item.created_at,
    )


async def _validated_feature_id(
    feature_id: Optional[str],
    workspace_id: ObjectId,
    feature_repo: FeatureRepository,
) -> Optional[ObjectId]:
    if feature_id is None:
        return None
    if not ObjectId.is_valid(feature_id):
        raise ValueError("Feature reference is invalid for this workspace")
    feature = await feature_repo.find_by_id(feature_id, workspace_id=workspace_id)
    if feature is None:
        raise ValueError("Feature reference is invalid for this workspace")
    return ObjectId(feature_id)


def _same_payload(existing: FeedbackItem, item: FeedbackItemCreate) -> bool:
    fields = {
        "title": "title",
        "description": "description",
        "source_url": "source_url",
        "customer_name": "customer_name",
        "customer_email": "customer_email",
        "company_name": "company_name",
        "category": "category",
        "sentiment": "sentiment",
        "source_priority": "source_priority",
        "tags": "tags",
        "feedback_date": "feedback_date",
        "promoted_feature_id": "promoted_feature_id",
    }
    for request_field, model_field in fields.items():
        if request_field not in item.model_fields_set:
            continue
        requested = getattr(item, request_field)
        stored = getattr(existing, model_field)
        requested = requested.value if hasattr(requested, "value") else requested
        stored = stored.value if hasattr(stored, "value") else stored
        if request_field == "promoted_feature_id" and stored is not None:
            stored = str(stored)
        if requested != stored:
            return False

    return (
        existing.external_id == item.external_id
        and existing.source_type == item.source_type
    )


async def _find_idempotent_item(
    feedback_repo: FeedbackRepository,
    workspace_id: ObjectId,
    item: FeedbackItemCreate,
) -> Optional[FeedbackItem]:
    if not item.external_id:
        return None
    return await feedback_repo.find_by_external_id(
        workspace_id,
        item.source_type,
        item.external_id,
    )


def _validation_errors(exc: ValidationError) -> List[FeedbackRowError]:
    errors = []
    for error in exc.errors(include_input=False, include_context=False)[:10]:
        field = (".".join(str(part) for part in error["loc"]) or "general")[:100]
        errors.append(FeedbackRowError(field=field, message=error["msg"][:200]))
    return errors


async def _record_feedback_audit(
    audit_repo: AuditLogRepository,
    workspace_id: ObjectId,
    actor: User,
    entity_id: str,
    description: str,
    action: AuditAction = AuditAction.CREATED,
) -> None:
    try:
        await audit_repo.create(
            AuditLog(
                workspace_id=workspace_id,
                actor=actor.name,
                user_id=actor.id,
                entity_type=AuditEntityType.FEEDBACK,
                entity_id=entity_id,
                action=action,
                description=description,
            )
        )
    except PyMongoError as exc:
        logger.exception("Feedback was stored but its audit record could not be saved")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback was stored, but audit logging failed. Contact an administrator.",
        ) from exc


async def _process_batch_row(
    row_number: int,
    raw_item: Dict[str, Any],
    workspace_id: ObjectId,
    batch_id: ObjectId,
    default_source_type: FeedbackSourceType,
    feature_repo: FeatureRepository,
    feedback_repo: FeedbackRepository,
) -> Tuple[FeedbackBatchRowResult, str, List[RowErrorSample]]:
    raw = dict(raw_item)
    client_id = raw.pop("id", None)
    try:
        if len(raw) > 20:
            raise ValueError("row contains too many fields")
        item = FeedbackItemCreate.model_validate(raw)
        if "sourceType" not in raw and "source_type" not in raw:
            item = item.model_copy(update={"source_type": default_source_type})
            item.model_fields_set.add("source_type")
        if not item.external_id and client_id is not None:
            if not isinstance(client_id, str) or not client_id.strip() or len(client_id.strip()) > 120:
                raise ValueError("id must be a non-empty string of at most 120 characters")
            item = item.model_copy(update={"external_id": client_id.strip()})
            item.model_fields_set.add("external_id")
        if not item.external_id:
            raise ValueError("externalId or id is required for safe retries")

        feedback, created = await _create_feedback(
            item,
            workspace_id,
            batch_id,
            feature_repo,
            feedback_repo,
        )
        outcome = "accepted" if created else "duplicate"
        return (
            FeedbackBatchRowResult(
                rowNumber=row_number,
                status=outcome,
                feedbackId=str(feedback.id),
            ),
            outcome,
            [],
        )
    except ValidationError as exc:
        errors = _validation_errors(exc)
    except ValueError as exc:
        message = str(exc)[:200]
        field = "general"
        if message.startswith("id "):
            field = "id"
        elif message.startswith("externalId"):
            field = "externalId"
        elif message.startswith("Feature reference"):
            field = "promotedFeatureId"
        errors = [FeedbackRowError(field=field, message=message)]

    return (
        FeedbackBatchRowResult(rowNumber=row_number, status="rejected", errors=errors),
        "rejected",
        [
            RowErrorSample(
                rowNumber=row_number,
                field=errors[0].field if errors else "general",
                message=errors[0].message[:200] if errors else "Row was rejected",
            )
        ],
    )


async def _create_feedback(
    item: FeedbackItemCreate,
    workspace_id: ObjectId,
    batch_id: Optional[ObjectId],
    feature_repo: FeatureRepository,
    feedback_repo: FeedbackRepository,
) -> Tuple[FeedbackItem, bool]:
    feature_id = await _validated_feature_id(
        item.promoted_feature_id,
        workspace_id,
        feature_repo,
    )
    existing = await _find_idempotent_item(feedback_repo, workspace_id, item)
    if existing is not None:
        if _same_payload(existing, item):
            return existing, False
        raise ValueError("externalId is already associated with different feedback")

    record = FeedbackItem(
        workspace_id=workspace_id,
        batch_id=batch_id,
        external_id=item.external_id,
        source_type=item.source_type,
        source_url=item.source_url,
        title=item.title,
        description=item.description,
        customer_name=item.customer_name,
        customer_email=item.customer_email,
        company_name=item.company_name,
        category=item.category,
        sentiment=item.sentiment,
        source_priority=item.source_priority,
        tags=item.tags,
        feedback_date=item.feedback_date,
        promoted_feature_id=feature_id,
    )
    try:
        return await feedback_repo.create(record), True
    except DuplicateEntityError:
        existing = await _find_idempotent_item(feedback_repo, workspace_id, item)
        if existing is not None and _same_payload(existing, item):
            return existing, False
        raise ValueError("externalId is already associated with different feedback")


@router.post(
    "",
    response_model=FeedbackItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create feedback",
)
async def create_feedback(
    payload: FeedbackItemCreate,
    response: Response,
    workspace_id: str = Query(..., alias="workspaceId"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key", max_length=120),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    feature_repo: FeatureRepository = Depends(get_feature_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> FeedbackItemResponse:
    workspace = await _load_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    if payload.source_type != FeedbackSourceType.MANUAL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Manual feedback must use sourceType 'manual'",
        )

    key = idempotency_key.strip() if idempotency_key else None
    if key == "":
        key = None
    if key and payload.external_id and key != payload.external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Idempotency-Key must match externalId when both are provided",
        )
    if key and not payload.external_id:
        payload = payload.model_copy(update={"external_id": key})
        payload.model_fields_set.add("external_id")
    if not payload.external_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="externalId or Idempotency-Key is required",
        )

    try:
        item, created = await _create_feedback(
            payload,
            workspace.id,
            None,
            feature_repo,
            feedback_repo,
        )
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_422_UNPROCESSABLE_CONTENT
            if detail.startswith("Feature reference")
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=detail) from exc

    if created:
        await _record_feedback_audit(
            audit_repo,
            workspace.id,
            current_user,
            str(item.id),
            "Feedback item created",
        )
    else:
        response.status_code = status.HTTP_200_OK
    return _feedback_response(item)


@router.get("", response_model=FeedbackListResponse, summary="List workspace feedback")
async def list_feedback(
    workspace_id: str = Query(..., alias="workspaceId"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    category: Optional[FeedbackCategory] = Query(default=None),
    sentiment: Optional[FeedbackSentiment] = Query(default=None),
    priority: Optional[FeedbackPriority] = Query(default=None),
    linked: Optional[bool] = Query(default=None, alias="linkedFeature"),
    sort: Literal["newest", "oldest", "priority"] = Query(default="newest"),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
) -> FeedbackListResponse:
    workspace = await _load_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    items, total = await feedback_repo.find_page(
        workspace.id,
        page=page,
        limit=limit,
        search=search.strip() if search and search.strip() else None,
        category=category,
        sentiment=sentiment,
        priority=priority,
        linked=linked,
        sort=sort,
    )
    return FeedbackListResponse(
        items=[_feedback_response(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit,
    )


@router.post(
    "/batch",
    response_model=FeedbackBatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a bounded feedback batch",
)
async def ingest_feedback_batch(
    payload: FeedbackBatchRequest,
    response: Response,
    workspace_id: str = Query(..., alias="workspaceId"),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    batch_repo: FeedbackBatchRepository = Depends(get_feedback_batch_repository),
    feature_repo: FeatureRepository = Depends(get_feature_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> FeedbackBatchIngestResponse:
    workspace = await _load_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    batch = await batch_repo.create(
        FeedbackBatch(
            workspace_id=workspace.id,
            uploaded_by=current_user.id,
            source_type=FeedbackSourceType.JSON,
            file_name="api-batch.json",
            status="processing",
            total_rows=len(payload.items),
        )
    )

    results: List[FeedbackBatchRowResult] = []
    accepted = duplicate = rejected = 0
    row_errors: List[RowErrorSample] = []

    for row_number, raw_item in enumerate(payload.items, start=1):
        try:
            result, outcome, errors = await _process_batch_row(
                row_number,
                raw_item,
                workspace.id,
                batch.id,
                FeedbackSourceType.JSON,
                feature_repo,
                feedback_repo,
            )
        except PyMongoError:
            logger.exception(
                "Feedback batch %s stopped after storage failure at row %d",
                batch.id,
                row_number,
            )
            for failed_row in range(row_number, len(payload.items) + 1):
                result = FeedbackBatchRowResult(
                    rowNumber=failed_row,
                    status="rejected",
                    errors=[
                        FeedbackRowError(
                            field="storage",
                            message="Storage unavailable; retry this row",
                        )
                    ],
                )
                results.append(result)
                row_errors.append(
                    RowErrorSample(
                        rowNumber=failed_row,
                        field="storage",
                        message="Storage unavailable; retry this row",
                    )
                )
            rejected += len(payload.items) - row_number + 1
            break
        results.append(result)
        row_errors.extend(errors)
        if outcome == "accepted":
            accepted += 1
        elif outcome == "duplicate":
            duplicate += 1
        else:
            rejected += 1

    final_status = "completed" if rejected == 0 else (
        "partial" if accepted + duplicate > 0 else "failed"
    )
    completed_at = datetime.now(timezone.utc)
    updated = await batch_repo.update(
        batch.id,
        {
            "status": final_status,
            "acceptedRows": accepted,
            "rejectedRows": rejected,
            "duplicateRows": duplicate,
            "errorSummary": [error.model_dump(by_alias=True) for error in row_errors],
            "completedAt": completed_at,
        },
        workspace_id=workspace.id,
    )
    if updated is None:
        logger.error("Feedback batch %s disappeared before completion", batch.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Feedback batch could not be finalized",
        )

    await _record_feedback_audit(
        audit_repo,
        workspace.id,
        current_user,
        str(batch.id),
        f"Feedback batch processed: {accepted} accepted, {duplicate} duplicate, {rejected} rejected",
    )
    response.status_code = status.HTTP_201_CREATED
    return FeedbackBatchIngestResponse(
        id=str(batch.id),
        workspaceId=str(workspace.id),
        status=final_status,
        totalRows=len(payload.items),
        acceptedRows=accepted,
        rejectedRows=rejected,
        duplicateRows=duplicate,
        results=results,
    )


@router.post(
    "/batch/{batch_id}/retry",
    response_model=FeedbackBatchIngestResponse,
    summary="Retry rejected feedback rows",
)
async def retry_feedback_batch(
    batch_id: str,
    payload: FeedbackBatchRetryRequest,
    workspace_id: str = Query(..., alias="workspaceId"),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
    batch_repo: FeedbackBatchRepository = Depends(get_feedback_batch_repository),
    feature_repo: FeatureRepository = Depends(get_feature_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> FeedbackBatchIngestResponse:
    workspace = await _load_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    if not ObjectId.is_valid(batch_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    existing_batch = await batch_repo.find_by_workspace_and_id(batch_id, workspace.id)
    if existing_batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    row_numbers = [row.row_number for row in payload.items]
    if len(set(row_numbers)) != len(row_numbers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A row may only be retried once per request",
        )
    failed_rows = {error.row_number for error in existing_batch.error_summary}
    if any(row_number not in failed_rows for row_number in row_numbers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only previously rejected rows may be retried",
        )

    batch = await batch_repo.claim_failed_batch(batch_id, workspace.id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch is not retryable or a retry is already processing",
        )

    accepted = duplicate = rejected_again = 0
    results: List[FeedbackBatchRowResult] = []
    new_errors: List[RowErrorSample] = []
    retry_set = set(row_numbers)
    remaining_errors = [
        error for error in batch.error_summary if error.row_number not in retry_set
    ]

    try:
        for row in payload.items:
            result, outcome, errors = await _process_batch_row(
                row.row_number,
                row.item,
                workspace.id,
                batch.id,
                batch.source_type,
                feature_repo,
                feedback_repo,
            )
            results.append(result)
            new_errors.extend(errors)
            if outcome == "accepted":
                accepted += 1
            elif outcome == "duplicate":
                duplicate += 1
            else:
                rejected_again += 1
    except PyMongoError as exc:
        logger.exception("Feedback batch retry could not complete")
        try:
            await batch_repo.update(
                batch.id,
                {"status": batch.status},
                workspace_id=workspace.id,
            )
        except PyMongoError:
            logger.exception("Feedback batch retry lock could not be released")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback batch retry could not be completed; retry the same rows later",
        ) from exc

    rejected = batch.rejected_rows - len(row_numbers) + rejected_again
    accepted_total = batch.accepted_rows + accepted
    duplicate_total = batch.duplicate_rows + duplicate
    final_status = "completed" if rejected == 0 else (
        "partial" if accepted_total + duplicate_total > 0 else "failed"
    )
    updated = await batch_repo.update(
        batch.id,
        {
            "status": final_status,
            "acceptedRows": accepted_total,
            "rejectedRows": rejected,
            "duplicateRows": duplicate_total,
            "errorSummary": [
                error.model_dump(by_alias=True)
                for error in remaining_errors + new_errors
            ],
            "completedAt": datetime.now(timezone.utc),
        },
        workspace_id=workspace.id,
    )
    if updated is None:
        logger.error("Feedback batch %s disappeared during retry", batch.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Feedback batch could not be finalized",
        )

    await _record_feedback_audit(
        audit_repo,
        workspace.id,
        current_user,
        str(batch.id),
        f"Feedback batch retry processed: {accepted} accepted, {duplicate} duplicate, {rejected_again} rejected",
        action=AuditAction.UPDATED,
    )
    return FeedbackBatchIngestResponse(
        id=str(batch.id),
        workspaceId=str(workspace.id),
        status=final_status,
        totalRows=batch.total_rows,
        acceptedRows=accepted_total,
        rejectedRows=rejected,
        duplicateRows=duplicate_total,
        results=results,
    )


@router.get(
    "/batch/{batch_id}",
    response_model=FeedbackBatchStatusResponse,
    summary="Get feedback batch status",
)
async def get_feedback_batch_status(
    batch_id: str,
    workspace_id: str = Query(..., alias="workspaceId"),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    batch_repo: FeedbackBatchRepository = Depends(get_feedback_batch_repository),
) -> FeedbackBatchStatusResponse:
    workspace = await _load_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    if not ObjectId.is_valid(batch_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    batch = await batch_repo.find_by_workspace_and_id(batch_id, workspace.id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return FeedbackBatchStatusResponse(
        id=str(batch.id),
        workspaceId=str(batch.workspace_id),
        status=batch.status,
        totalRows=batch.total_rows,
        acceptedRows=batch.accepted_rows,
        rejectedRows=batch.rejected_rows,
        duplicateRows=batch.duplicate_rows,
        errorSummary=[error.model_dump(by_alias=True) for error in batch.error_summary],
        startedAt=batch.started_at,
        completedAt=batch.completed_at,
    )


@router.get(
    "/{feedback_id}",
    response_model=FeedbackItemResponse,
    summary="Get feedback details",
)
async def get_feedback(
    feedback_id: str,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(get_workspace_membership_repository),
    feedback_repo: FeedbackRepository = Depends(get_feedback_repository),
) -> FeedbackItemResponse:
    if not ObjectId.is_valid(feedback_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    item = await feedback_repo.find_by_id(feedback_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    await _load_workspace(
        str(item.workspace_id),
        current_user,
        workspace_repo,
        membership_repo,
    )
    return _feedback_response(item)
