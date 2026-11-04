"""
ProductMind AI — Authentication & Session Management Automated Test Suite
Phase 2, Step 3 Verification.
Tests all 14 required authentication and security behaviors.
"""

from datetime import timedelta
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import verify_password, create_access_token
from app.database.collections import Collections
from app.database.connection import MongoDBManager


@pytest.fixture(scope="module")
def client():
    """Provides test client within application lifespan context."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def unique_test_user_data():
    """Generates a randomized user payload to ensure isolation."""
    unique_id = uuid.uuid4().hex[:8]
    return {
        "name": f"Test PM {unique_id}",
        "email": f"auth.test.{unique_id}@productmind.ai",
        "password": "SecurePassword123!",
        "avatar": "https://example.com/avatar.png",
        "theme": "dark",
        "reducedMotion": False,
    }


def test_1_successful_user_registration(client, unique_test_user_data):
    """1. Test successful user registration."""
    response = client.post("/api/v1/auth/register", json=unique_test_user_data)
    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == unique_test_user_data["email"]
    assert payload["name"] == unique_test_user_data["name"]
    assert "password" not in payload
    assert "passwordHash" not in payload
    assert "id" in payload


def test_2_duplicate_email_registration(client, unique_test_user_data):
    """2. Test duplicate email registration rejection."""
    response = client.post("/api/v1/auth/register", json=unique_test_user_data)
    assert response.status_code == 409
    payload = response.json()
    assert "already registered" in payload["detail"].lower()


def test_3_password_hashing_verification(client, unique_test_user_data):
    """3. Test password hashing in MongoDB: verify stored value is bcrypt and not plain-text."""
    db = MongoDBManager.get_database()
    stored_doc = db[Collections.USERS].find_one({"email": unique_test_user_data["email"]})
    assert stored_doc is not None
    assert stored_doc["passwordHash"] != unique_test_user_data["password"]
    assert stored_doc["passwordHash"].startswith("$2b$") or stored_doc["passwordHash"].startswith("$2a$")
    assert verify_password(unique_test_user_data["password"], stored_doc["passwordHash"]) is True


def test_4_successful_login(client, unique_test_user_data):
    """4. Test successful login and token issuance."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": unique_test_user_data["password"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "accessToken" in payload or "access_token" in payload
    assert "refreshToken" in payload or "refresh_token" in payload
    assert payload.get("tokenType", payload.get("token_type")) == "bearer"
    assert payload.get("expiresIn", payload.get("expires_in")) > 0

    user_info = payload["user"]
    assert user_info["email"] == unique_test_user_data["email"]
    assert "passwordHash" not in user_info


def test_5_login_with_incorrect_password(client, unique_test_user_data):
    """5. Test login with an incorrect password."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": "WrongPassword999!",
        },
    )
    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


def test_6_access_token_validation(client, unique_test_user_data):
    """6. Test access token validation on protected /auth/me endpoint."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": unique_test_user_data["password"],
        },
    )
    access_token = login_resp.json().get("accessToken") or login_resp.json().get("access_token")

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == unique_test_user_data["email"]


def test_7_missing_access_token(client):
    """7. Test missing access token returns 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_8_invalid_access_token(client):
    """8. Test invalid/malformed access token returns 401 Unauthorized."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.malformed.token.string"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


def test_9_expired_access_token(client, unique_test_user_data):
    """9. Test expired access token rejection."""
    # Obtain user doc to get real ID
    db = MongoDBManager.get_database()
    user_doc = db[Collections.USERS].find_one({"email": unique_test_user_data["email"]})
    session_doc = db[Collections.AUTH_SESSIONS].find_one({"userId": user_doc["_id"]})

    # Generate an expired token (negative expiration delta)
    expired_token, _ = create_access_token(
        user_id=str(user_doc["_id"]),
        session_id=str(session_doc["_id"]),
        session_family=session_doc["sessionFamily"],
        expires_delta=timedelta(seconds=-10),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_10_successful_refresh_token_rotation(client, unique_test_user_data):
    """10. Test successful refresh token exchange and rotation."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": unique_test_user_data["password"],
        },
    )
    initial_refresh = login_resp.json().get("refreshToken") or login_resp.json().get("refresh_token")

    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": initial_refresh},
    )
    assert refresh_resp.status_code == 200
    rotated_data = refresh_resp.json()
    new_access = rotated_data.get("accessToken") or rotated_data.get("access_token")
    new_refresh = rotated_data.get("refreshToken") or rotated_data.get("refresh_token")

    assert new_access is not None
    assert new_refresh is not None
    assert new_refresh != initial_refresh

    # Validate that new access token works
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me_resp.status_code == 200


def test_11_reuse_of_old_refresh_token(client, unique_test_user_data):
    """11. Test that reusing an old (already rotated) refresh token triggers family revocation."""
    # Step A: Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": unique_test_user_data["password"],
        },
    )
    token1 = login_resp.json().get("refreshToken") or login_resp.json().get("refresh_token")

    # Step B: Rotate once (token1 -> token2)
    refresh_resp1 = client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": token1},
    )
    assert refresh_resp1.status_code == 200
    token2 = refresh_resp1.json().get("refreshToken") or refresh_resp1.json().get("refresh_token")
    access2 = refresh_resp1.json().get("accessToken") or refresh_resp1.json().get("access_token")

    # Step C: Malicious/Replay attempt: try to reuse token1
    replay_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": token1},
    )
    assert replay_resp.status_code == 401
    assert "revoked" in replay_resp.json()["detail"].lower() or "reused" in replay_resp.json()["detail"].lower()

    # Step D: Confirm that token2 was also revoked as part of the family compromise
    token2_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": token2},
    )
    assert token2_resp.status_code == 401

    # Step E: Confirm access token2 is now rejected because session was revoked
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access2}"},
    )
    assert me_resp.status_code == 401
    assert "revoked" in me_resp.json()["detail"].lower()


def test_12_logout_and_session_invalidation(client, unique_test_user_data):
    """12. Test logout revokes session and invalidates access token."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": unique_test_user_data["password"],
        },
    )
    access_token = login_resp.json().get("accessToken") or login_resp.json().get("access_token")

    # Logout
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_resp.status_code == 200
    assert "logged out" in logout_resp.json()["message"].lower()

    # Verify that the same access token can no longer access /auth/me
    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 401
    assert "revoked" in me_resp.json()["detail"].lower()


def test_13_accessing_auth_me_with_valid_token(client, unique_test_user_data):
    """13. Test accessing /auth/me with a newly issued valid token."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": unique_test_user_data["email"],
            "password": unique_test_user_data["password"],
        },
    )
    access_token = login_resp.json().get("accessToken") or login_resp.json().get("access_token")

    me_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert profile["email"] == unique_test_user_data["email"]
    assert profile["name"] == unique_test_user_data["name"]
    assert "password" not in profile
    assert "passwordHash" not in profile


def test_14_accessing_auth_me_without_authentication(client):
    """14. Test accessing /auth/me without authentication header."""
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
    assert me_resp.headers.get("www-authenticate") == "Bearer"


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(unique_test_user_data):
    """Clean up only the test user and their test sessions created during this test module."""
    yield
    db = MongoDBManager.get_database()
    user_doc = db[Collections.USERS].find_one({"email": unique_test_user_data["email"]})
    if user_doc:
        db[Collections.AUTH_SESSIONS].delete_many({"userId": user_doc["_id"]})
        db[Collections.USERS].delete_one({"_id": user_doc["_id"]})
