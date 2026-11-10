from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies import (
    get_audit_log_repository,
    get_current_user,
    get_mongo_db,
    get_user_repository,
    get_workspace_membership_repository,
    get_workspace_repository,
)
from app.core.enums import MembershipStatus, PlatformRole, UserRole
from app.main import app
from app.models.auth import User, Workspace, WorkspaceMembership
from app.repositories import DuplicateEntityError

client = TestClient(app)

OWNER_ID = ObjectId("660011223344556677889901")
MEMBER_ID = ObjectId("660011223344556677889902")
WORKSPACE_ID = ObjectId("660011223344556677889903")


def make_user(user_id=OWNER_ID, name="Workspace Owner"):
    return User(
        id=user_id,
        name=name,
        email=f"{str(user_id)[-4:]}@productmind.test",
        password_hash="mock-password-hash",
        platform_role=PlatformRole.USER,
        is_active=True,
    )


def make_workspace(owner_id=OWNER_ID):
    return Workspace(
        id=WORKSPACE_ID,
        name="Product Team",
        slug="product-team",
        owner_id=owner_id,
        created_at=datetime.now(timezone.utc),
    )


def make_membership(user_id=OWNER_ID, role=UserRole.ADMIN, status=MembershipStatus.ACTIVE):
    return WorkspaceMembership(
        id=ObjectId("660011223344556677889904"),
        workspace_id=WORKSPACE_ID,
        user_id=user_id,
        role=role,
        status=status,
    )


@pytest.fixture
def api_state():
    app.dependency_overrides.clear()
    user = make_user()
    workspace_repo = AsyncMock()
    membership_repo = AsyncMock()
    user_repo = AsyncMock()
    audit_repo = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_workspace_repository] = lambda: workspace_repo
    app.dependency_overrides[get_workspace_membership_repository] = lambda: membership_repo
    app.dependency_overrides[get_user_repository] = lambda: user_repo
    app.dependency_overrides[get_audit_log_repository] = lambda: audit_repo

    yield {
        "user": user,
        "workspace_repo": workspace_repo,
        "membership_repo": membership_repo,
        "user_repo": user_repo,
        "audit_repo": audit_repo,
    }

    app.dependency_overrides.clear()


def test_workspace_creation_assigns_creator_as_owner_and_admin(api_state):
    workspace = make_workspace()
    api_state["workspace_repo"].create.return_value = workspace

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Product Team", "slug": "Product-Team"},
    )

    assert response.status_code == 201
    assert response.json()["ownerId"] == str(OWNER_ID)
    assert response.json()["plan"] == "Starter Tier"
    saved_membership = api_state["membership_repo"].create.await_args.args[0]
    assert saved_membership.user_id == OWNER_ID
    assert saved_membership.role == UserRole.ADMIN
    assert saved_membership.status == MembershipStatus.ACTIVE
    api_state["audit_repo"].create.assert_awaited_once()


def test_workspace_creation_rejects_duplicate_slug(api_state):
    api_state["workspace_repo"].create.side_effect = DuplicateEntityError("duplicate")

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Product Team", "slug": "product-team"},
    )

    assert response.status_code == 409
    api_state["membership_repo"].create.assert_not_awaited()


def test_workspace_creation_rejects_client_selected_plan(api_state):
    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Product Team", "slug": "product-team", "plan": "Enterprise Tier"},
    )

    assert response.status_code == 422
    api_state["workspace_repo"].create.assert_not_awaited()


def test_workspace_list_is_scoped_to_owner_and_active_memberships(api_state):
    membership = make_membership(user_id=MEMBER_ID, role=UserRole.PRODUCT_MANAGER)
    workspace = make_workspace(owner_id=MEMBER_ID)
    api_state["membership_repo"].find_user_memberships.return_value = [membership]
    api_state["workspace_repo"].find_accessible.return_value = [workspace]

    response = client.get("/api/v1/workspaces")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(WORKSPACE_ID)]
    api_state["workspace_repo"].find_accessible.assert_awaited_once_with(
        OWNER_ID,
        [WORKSPACE_ID],
        skip=0,
        limit=50,
    )


def test_non_member_cannot_retrieve_workspace(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace(owner_id=MEMBER_ID)
    api_state["membership_repo"].find_membership.return_value = None

    response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_inactive_member_cannot_retrieve_workspace(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace(owner_id=MEMBER_ID)
    api_state["membership_repo"].find_membership.return_value = make_membership(
        user_id=OWNER_ID,
        status=MembershipStatus.INACTIVE,
    )

    response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}")

    assert response.status_code == 404


def test_workspace_member_cannot_update_settings(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace(owner_id=MEMBER_ID)
    api_state["membership_repo"].find_membership.return_value = make_membership(
        user_id=OWNER_ID,
        role=UserRole.PRODUCT_MANAGER,
    )

    response = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}",
        json={"name": "Renamed"},
    )

    assert response.status_code == 403
    api_state["workspace_repo"].update.assert_not_awaited()


def test_workspace_owner_can_update_name_and_settings(api_state):
    workspace = make_workspace()
    updated_workspace = make_workspace()
    updated_workspace.name = "Renamed"
    api_state["workspace_repo"].find_by_id.return_value = workspace
    api_state["workspace_repo"].update.return_value = updated_workspace
    api_state["membership_repo"].find_membership.return_value = make_membership()

    response = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}",
        json={"name": "Renamed"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"
    api_state["workspace_repo"].update.assert_awaited_once()
    api_state["audit_repo"].create.assert_awaited_once()


def test_workspace_settings_patch_preserves_unmentioned_values(api_state):
    workspace = make_workspace()
    updated_workspace = make_workspace()
    updated_workspace.settings.default_theme = "light"
    api_state["workspace_repo"].find_by_id.return_value = workspace
    api_state["workspace_repo"].update.return_value = updated_workspace
    api_state["membership_repo"].find_membership.return_value = make_membership()

    response = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}",
        json={"settings": {"defaultTheme": "light"}},
    )

    assert response.status_code == 200
    updates = api_state["workspace_repo"].update.await_args.args[1]
    assert updates["settings"] == {
        "defaultTheme": "light",
        "reducedMotion": False,
        "allowGuestViewers": True,
    }


def test_admin_cannot_assign_admin_role(api_state):
    api_state["user"].id = MEMBER_ID
    api_state["workspace_repo"].find_by_id.return_value = make_workspace(owner_id=OWNER_ID)
    api_state["membership_repo"].find_membership.return_value = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.ADMIN,
    )

    response = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members",
        json={"email": "new.person@productmind.test", "role": UserRole.ADMIN.value},
    )

    assert response.status_code == 403
    api_state["user_repo"].find_by_email.assert_not_awaited()


def test_owner_can_promote_existing_member_to_admin(api_state):
    member = make_membership(user_id=MEMBER_ID, role=UserRole.PRODUCT_MANAGER)
    promoted = make_membership(user_id=MEMBER_ID, role=UserRole.ADMIN)
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()
    api_state["membership_repo"].find_membership.side_effect = [
        make_membership(),
        member,
    ]
    api_state["membership_repo"].update_active_role.return_value = promoted
    api_state["user_repo"].find_public_profiles.return_value = {
        str(MEMBER_ID): {"name": "Member", "avatar": None}
    }

    response = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBER_ID}",
        json={"role": UserRole.ADMIN.value},
    )

    assert response.status_code == 200
    assert response.json()["role"] == UserRole.ADMIN.value
    api_state["membership_repo"].update_active_role.assert_awaited_once_with(
        WORKSPACE_ID,
        str(MEMBER_ID),
        UserRole.ADMIN,
    )
    api_state["audit_repo"].create.assert_awaited_once()


def test_duplicate_active_membership_is_rejected(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()
    api_state["membership_repo"].find_membership.return_value = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.PRODUCT_MANAGER,
    )
    api_state["user_repo"].find_by_email.return_value = make_user(MEMBER_ID, "Existing Member")

    response = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members",
        json={"email": "member@productmind.test"},
    )

    assert response.status_code == 409
    api_state["membership_repo"].create.assert_not_awaited()


def test_owner_can_add_existing_user_without_exposing_email(api_state):
    workspace = make_workspace()
    target_user = make_user(MEMBER_ID, "New Member")
    target_membership = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.PRODUCT_MANAGER,
    )
    api_state["workspace_repo"].find_by_id.return_value = workspace
    api_state["membership_repo"].find_membership.return_value = None
    api_state["membership_repo"].create.return_value = target_membership
    api_state["user_repo"].find_by_email.return_value = target_user

    response = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members",
        json={"email": target_user.email},
    )

    assert response.status_code == 201
    member_data = response.json()
    assert member_data["userId"] == str(MEMBER_ID)
    assert member_data["role"] == UserRole.PRODUCT_MANAGER.value
    assert "email" not in member_data
    assert "passwordHash" not in member_data
    api_state["audit_repo"].create.assert_awaited_once()


def test_owner_can_reactivate_inactive_member(api_state):
    inactive_membership = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.VIEWER,
        status=MembershipStatus.INACTIVE,
    )
    active_membership = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.PRODUCT_MANAGER,
    )
    target_user = make_user(MEMBER_ID, "Returning Member")
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()
    api_state["membership_repo"].find_membership.side_effect = [
        None,
        inactive_membership,
    ]
    api_state["membership_repo"].reactivate_membership.return_value = active_membership
    api_state["user_repo"].find_by_email.return_value = target_user

    response = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members",
        json={"email": target_user.email, "role": UserRole.PRODUCT_MANAGER.value},
    )

    assert response.status_code == 201
    api_state["membership_repo"].reactivate_membership.assert_awaited_once_with(
        WORKSPACE_ID,
        MEMBER_ID,
        UserRole.PRODUCT_MANAGER,
        OWNER_ID,
    )


def test_member_list_returns_only_safe_active_profiles(api_state):
    membership = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.PRODUCT_MANAGER,
    )
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()
    api_state["membership_repo"].find_workspace_memberships.return_value = [membership]
    api_state["user_repo"].find_public_profiles.return_value = {
        str(MEMBER_ID): {"name": "Member", "avatar": None}
    }

    response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/members")

    assert response.status_code == 200
    member_data = response.json()[0]
    assert member_data["userId"] == str(MEMBER_ID)
    assert member_data["status"] == MembershipStatus.ACTIVE.value
    assert "email" not in member_data
    assert "passwordHash" not in member_data


def test_owner_cannot_demote_themselves(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()

    response = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{OWNER_ID}",
        json={"role": UserRole.VIEWER.value},
    )

    assert response.status_code == 409
    api_state["membership_repo"].update_active_role.assert_not_awaited()


def test_workspace_owner_cannot_be_removed(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()
    api_state["membership_repo"].find_membership.return_value = make_membership()

    response = client.delete(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{OWNER_ID}"
    )

    assert response.status_code == 409
    api_state["membership_repo"].deactivate_active_member.assert_not_awaited()


def test_member_removal_deactivates_instead_of_deleting(api_state):
    target_membership = make_membership(user_id=MEMBER_ID, role=UserRole.PRODUCT_MANAGER)
    deactivated = make_membership(
        user_id=MEMBER_ID,
        role=UserRole.PRODUCT_MANAGER,
        status=MembershipStatus.INACTIVE,
    )
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()
    api_state["membership_repo"].find_membership.return_value = target_membership
    api_state["membership_repo"].deactivate_active_member.return_value = deactivated

    response = client.delete(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBER_ID}"
    )

    assert response.status_code == 204
    api_state["membership_repo"].deactivate_active_member.assert_awaited_once_with(
        WORKSPACE_ID,
        str(MEMBER_ID),
    )
    api_state["membership_repo"].delete.assert_not_awaited()
    api_state["audit_repo"].create.assert_awaited_once()


def test_workspace_owner_cannot_leave(api_state):
    api_state["workspace_repo"].find_by_id.return_value = make_workspace()

    response = client.delete(f"/api/v1/workspaces/{WORKSPACE_ID}/members/me")

    assert response.status_code == 409
    api_state["membership_repo"].deactivate_active_member.assert_not_awaited()


def test_unauthenticated_workspace_request_returns_401():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_mongo_db] = lambda: MagicMock()

    response = client.get("/api/v1/workspaces")

    assert response.status_code == 401
    app.dependency_overrides.clear()
