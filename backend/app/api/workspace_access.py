from typing import Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.enums import MembershipStatus, PlatformRole
from app.models.auth import User, Workspace, WorkspaceMembership
from app.repositories.user_repository import WorkspaceMembershipRepository
from app.repositories.workspace_repository import WorkspaceRepository


async def load_accessible_workspace(
    workspace_id: str,
    user: User,
    workspace_repo: WorkspaceRepository,
    membership_repo: WorkspaceMembershipRepository,
) -> Tuple[Workspace, Optional[WorkspaceMembership], bool, bool]:
    if not ObjectId.is_valid(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID",
        )

    workspace = await workspace_repo.find_by_id(workspace_id)
    if not workspace or workspace.is_archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    is_owner = str(workspace.owner_id) == str(user.id)
    is_platform_admin = user.platform_role == PlatformRole.PLATFORM_ADMIN
    membership = await membership_repo.find_membership(workspace.id, user.id)
    is_active_member = membership is not None and membership.status == MembershipStatus.ACTIVE

    if not (is_owner or is_platform_admin or is_active_member):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    return workspace, membership, is_owner, is_platform_admin
