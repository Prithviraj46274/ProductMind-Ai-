"""
Workspace management endpoints with membership-scoped access control.
"""

import logging
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pymongo.errors import PyMongoError

from app.api.dependencies import (
    get_audit_log_repository,
    get_current_user,
    get_user_repository,
    get_workspace_membership_repository,
    get_workspace_repository,
)
from app.api.workspace_access import load_accessible_workspace as _load_accessible_workspace
from app.core.enums import (
    AuditAction,
    AuditEntityType,
    MembershipStatus,
    PlatformRole,
    UserRole,
    WorkspacePlan,
)
from app.models.audit import AuditLog
from app.models.auth import (
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceSettings,
)
from app.repositories import (
    AuditLogRepository,
    DuplicateEntityError,
    UserRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
    WorkspaceResponse,
    WorkspaceSettingsDTO,
    WorkspaceUpdate,
)

logger = logging.getLogger("productmind.api.workspaces")

router = APIRouter(prefix="/workspaces", tags=["Workspace Management"])


def _require_workspace_admin(
    membership: Optional[WorkspaceMembership],
    is_owner: bool,
    is_platform_admin: bool,
) -> None:
    if (
        not is_owner
        and not is_platform_admin
        and (membership is None or membership.role != UserRole.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace owner or admin permission is required",
        )


def _workspace_response(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=str(workspace.id),
        name=workspace.name,
        slug=workspace.slug,
        owner_id=str(workspace.owner_id),
        plan=workspace.plan,
        settings=WorkspaceSettingsDTO.model_validate(
            workspace.settings.model_dump(by_alias=True)
        ),
        is_archived=workspace.is_archived,
        created_at=workspace.created_at,
    )


def _member_response(
    membership: WorkspaceMembership,
    public_profile: dict,
) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        user_id=str(membership.user_id),
        name=public_profile["name"],
        avatar=public_profile.get("avatar"),
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
    )


async def _record_workspace_audit(
    audit_repo: AuditLogRepository,
    workspace: Workspace,
    actor: User,
    action: AuditAction,
    description: str,
    previous_state: Optional[dict] = None,
    new_state: Optional[dict] = None,
) -> None:
    try:
        await audit_repo.create(
            AuditLog(
                workspace_id=workspace.id,
                actor=actor.name,
                user_id=actor.id,
                entity_type=AuditEntityType.WORKSPACE,
                entity_id=str(workspace.id),
                action=action,
                description=description,
                previous_state=previous_state,
                new_state=new_state,
            )
        )
    except PyMongoError as exc:
        logger.exception("Workspace change succeeded but its audit record could not be saved")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Workspace change succeeded, but audit logging failed. Contact an administrator.",
        ) from exc


async def _deactivate_member(
    workspace: Workspace,
    target_user_id: str,
    actor: User,
    membership_repo: WorkspaceMembershipRepository,
    audit_repo: AuditLogRepository,
) -> None:
    if str(workspace.owner_id) == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The workspace owner cannot be removed or deactivated",
        )

    target_membership = await membership_repo.find_membership(
        workspace.id,
        target_user_id,
    )
    if target_membership is None or target_membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace member not found",
        )

    if (
        target_membership.role == UserRole.ADMIN
        and str(actor.id) != str(workspace.owner_id)
        and actor.platform_role != PlatformRole.PLATFORM_ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can remove another workspace admin",
        )

    deactivated = await membership_repo.deactivate_active_member(
        workspace.id,
        target_user_id,
    )
    if deactivated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace member not found",
        )

    await _record_workspace_audit(
        audit_repo,
        workspace,
        actor,
        AuditAction.UPDATED,
        "Workspace member deactivated",
        previous_state={
            "userId": str(target_membership.user_id),
            "role": target_membership.role.value,
            "status": target_membership.status.value,
        },
        new_state={
            "userId": str(deactivated.user_id),
            "role": deactivated.role.value,
            "status": deactivated.status.value,
        },
    )


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> WorkspaceResponse:
    workspace = Workspace(
        name=payload.name,
        slug=payload.slug,
        owner_id=current_user.id,
        plan=WorkspacePlan.STARTER,
        settings=(
            WorkspaceSettings(**payload.settings.model_dump(by_alias=True))
            if payload.settings
            else WorkspaceSettings()
        ),
    )

    try:
        created_workspace = await workspace_repo.create(workspace)
    except DuplicateEntityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace slug is already in use",
        ) from exc

    owner_membership = WorkspaceMembership(
        workspace_id=created_workspace.id,
        user_id=current_user.id,
        role=UserRole.ADMIN,
        status=MembershipStatus.ACTIVE,
        invited_by=current_user.id,
    )
    try:
        await membership_repo.create(owner_membership)
    except (DuplicateEntityError, PyMongoError) as exc:
        try:
            await workspace_repo.delete(created_workspace.id)
        except PyMongoError:
            logger.exception(
                "Failed to clean up workspace after owner membership creation failed"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workspace creation failed and requires administrator recovery.",
            ) from exc
        if isinstance(exc, DuplicateEntityError):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace membership already exists",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace could not be created because owner membership setup failed",
        ) from exc

    await _record_workspace_audit(
        audit_repo,
        created_workspace,
        current_user,
        AuditAction.CREATED,
        "Workspace created",
        new_state={"name": created_workspace.name, "slug": created_workspace.slug},
    )
    return _workspace_response(created_workspace)


@router.get(
    "",
    response_model=List[WorkspaceResponse],
    summary="List accessible workspaces",
)
async def list_workspaces(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
) -> List[WorkspaceResponse]:
    memberships = await membership_repo.find_user_memberships(current_user.id)
    workspaces = await workspace_repo.find_accessible(
        current_user.id,
        [membership.workspace_id for membership in memberships],
        skip=skip,
        limit=limit,
    )
    return [_workspace_response(workspace) for workspace in workspaces]


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace details",
)
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
) -> WorkspaceResponse:
    workspace, _, _, _ = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    return _workspace_response(workspace)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace settings",
)
async def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> WorkspaceResponse:
    workspace, membership, is_owner, is_platform_admin = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    _require_workspace_admin(membership, is_owner, is_platform_admin)

    updates = payload.model_dump(exclude_unset=True)
    if payload.settings is not None:
        settings = workspace.settings.model_dump(by_alias=True)
        settings.update(payload.settings.model_dump(by_alias=True, exclude_unset=True))
        updates["settings"] = settings
    previous_state = {
        "name": workspace.name,
        "settings": workspace.settings.model_dump(by_alias=True),
    }

    updated_workspace = await workspace_repo.update(workspace.id, updates)
    if updated_workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    await _record_workspace_audit(
        audit_repo,
        updated_workspace,
        current_user,
        AuditAction.UPDATED,
        "Workspace settings updated",
        previous_state=previous_state,
        new_state={
            "name": updated_workspace.name,
            "settings": updated_workspace.settings.model_dump(by_alias=True),
        },
    )
    return _workspace_response(updated_workspace)


@router.get(
    "/{workspace_id}/members",
    response_model=List[WorkspaceMemberResponse],
    summary="List workspace members",
)
async def list_workspace_members(
    workspace_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    user_repo: UserRepository = Depends(get_user_repository),
) -> List[WorkspaceMemberResponse]:
    workspace, _, _, _ = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    memberships = await membership_repo.find_workspace_memberships(
        workspace.id,
        skip=skip,
        limit=limit,
    )
    profiles = await user_repo.find_public_profiles(
        [membership.user_id for membership in memberships]
    )
    return [
        _member_response(membership, profiles[str(membership.user_id)])
        for membership in memberships
        if str(membership.user_id) in profiles
    ]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an existing user to a workspace",
)
async def add_workspace_member(
    workspace_id: str,
    payload: WorkspaceMemberAdd,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> WorkspaceMemberResponse:
    workspace, membership, is_owner, is_platform_admin = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    _require_workspace_admin(membership, is_owner, is_platform_admin)

    if (
        payload.role == UserRole.ADMIN
        and not is_owner
        and not is_platform_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can add a workspace admin",
        )

    target_user = await user_repo.find_by_email(payload.email)
    if target_user is None or not target_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active user not found",
        )

    existing_membership = await membership_repo.find_membership(
        workspace.id,
        target_user.id,
    )
    if existing_membership and existing_membership.status != MembershipStatus.INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a workspace membership",
        )

    if existing_membership:
        added_membership = await membership_repo.reactivate_membership(
            workspace.id,
            target_user.id,
            payload.role,
            current_user.id,
        )
        if added_membership is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace membership changed; retry the request",
            )
        action = AuditAction.UPDATED
        description = "Workspace member reactivated"
    else:
        try:
            added_membership = await membership_repo.create(
                WorkspaceMembership(
                    workspace_id=workspace.id,
                    user_id=target_user.id,
                    role=payload.role,
                    status=MembershipStatus.ACTIVE,
                    invited_by=current_user.id,
                )
            )
        except DuplicateEntityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has a workspace membership",
            ) from exc
        action = AuditAction.CREATED
        description = "Workspace member added"

    await _record_workspace_audit(
        audit_repo,
        workspace,
        current_user,
        action,
        description,
        new_state={
            "userId": str(added_membership.user_id),
            "role": added_membership.role.value,
            "status": added_membership.status.value,
        },
    )
    return _member_response(
        added_membership,
        {
            "name": target_user.name,
            "avatar": target_user.avatar,
        },
    )


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Change a workspace member role",
)
async def update_workspace_member_role(
    workspace_id: str,
    user_id: str,
    payload: WorkspaceMemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    user_repo: UserRepository = Depends(get_user_repository),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> WorkspaceMemberResponse:
    workspace, membership, is_owner, is_platform_admin = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    _require_workspace_admin(membership, is_owner, is_platform_admin)
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")
    if str(workspace.owner_id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The workspace owner's role cannot be changed",
        )

    target_membership = await membership_repo.find_membership(workspace.id, user_id)
    if target_membership is None or target_membership.status != MembershipStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace member not found",
        )
    if (
        target_membership.role == UserRole.ADMIN
        and not is_owner
        and not is_platform_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can change another workspace admin's role",
        )
    if (
        payload.role == UserRole.ADMIN
        and not is_owner
        and not is_platform_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can assign the workspace admin role",
        )

    profiles = await user_repo.find_public_profiles([target_membership.user_id])
    profile = profiles.get(str(target_membership.user_id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace member profile not found",
        )

    updated_membership = await membership_repo.update_active_role(
        workspace.id,
        user_id,
        payload.role,
    )
    if updated_membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active workspace member not found",
        )

    await _record_workspace_audit(
        audit_repo,
        workspace,
        current_user,
        AuditAction.UPDATED,
        "Workspace member role changed",
        previous_state={
            "userId": str(target_membership.user_id),
            "role": target_membership.role.value,
        },
        new_state={
            "userId": str(updated_membership.user_id),
            "role": updated_membership.role.value,
        },
    )
    return _member_response(updated_membership, profile)


@router.delete(
    "/{workspace_id}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a workspace",
)
async def leave_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> Response:
    workspace, _, is_owner, _ = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    if is_owner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The workspace owner cannot leave without transferring ownership",
        )
    await _deactivate_member(
        workspace,
        str(current_user.id),
        current_user,
        membership_repo,
        audit_repo,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a workspace member",
)
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    workspace_repo: WorkspaceRepository = Depends(get_workspace_repository),
    membership_repo: WorkspaceMembershipRepository = Depends(
        get_workspace_membership_repository
    ),
    audit_repo: AuditLogRepository = Depends(get_audit_log_repository),
) -> Response:
    workspace, membership, is_owner, is_platform_admin = await _load_accessible_workspace(
        workspace_id,
        current_user,
        workspace_repo,
        membership_repo,
    )
    _require_workspace_admin(membership, is_owner, is_platform_admin)
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")
    await _deactivate_member(
        workspace,
        user_id,
        current_user,
        membership_repo,
        audit_repo,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
