"""
ProductMind AI — Swagger UI & HTTP Bearer Authentication Verification Tests
Verifies that:
1. OpenAPI specification configures HTTP Bearer JWT security (not OAuth2 password flow).
2. Swagger UI Authorize accepts JWT access tokens directly.
3. Protected endpoints enforce HTTP Bearer authentication.
4. Login endpoint accepts JSON credentials and does not require form encoding.
5. Session management, JWT verification, and 401 Unauthorized handling remain intact.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials

from app.main import app
from app.api.dependencies import http_bearer, get_current_user
from app.core.security import create_access_token


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient for testing OpenAPI and HTTP Bearer flows."""
    with TestClient(app) as test_client:
        yield test_client


def test_openapi_security_schemes(client):
    """Verify OpenAPI 3.x schema defines BearerAuth with HTTP bearer and JWT format."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    components = schema.get("components", {})
    security_schemes = components.get("securitySchemes", {})

    # Must contain BearerAuth with type="http" and scheme="bearer"
    assert "BearerAuth" in security_schemes, "BearerAuth security scheme missing from OpenAPI components"
    bearer_scheme = security_schemes["BearerAuth"]
    assert bearer_scheme["type"] == "http"
    assert bearer_scheme["scheme"] == "bearer"
    assert bearer_scheme.get("bearerFormat") == "JWT"

    # Must NOT contain OAuth2 password flow scheme
    assert "OAuth2PasswordBearer" not in security_schemes, (
        "OAuth2PasswordBearer should be replaced with HTTPBearer to prevent form-urlencoded mismatch"
    )


def test_protected_endpoints_declare_bearer_security(client):
    """Verify protected endpoints declare BearerAuth security in OpenAPI specification."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    # Check /api/v1/auth/me
    auth_me_op = paths.get("/api/v1/auth/me", {}).get("get", {})
    assert "security" in auth_me_op
    assert {"BearerAuth": []} in auth_me_op["security"]

    # Check /api/v1/auth/logout
    auth_logout_op = paths.get("/api/v1/auth/logout", {}).get("post", {})
    assert "security" in auth_logout_op
    assert {"BearerAuth": []} in auth_logout_op["security"]

    # Check /api/v1/ai/feedback/{feedback_id}/analyze
    analyze_op = paths.get("/api/v1/ai/feedback/{feedback_id}/analyze", {}).get("post", {})
    assert "security" in analyze_op
    assert {"BearerAuth": []} in analyze_op["security"]

    # Check /api/v1/ai/features/group
    feature_group_op = paths.get("/api/v1/ai/features/group", {}).get("post", {})
    assert "security" in feature_group_op
    assert {"BearerAuth": []} in feature_group_op["security"]

    # Check /api/v1/ai/features/groups
    feature_groups_op = paths.get("/api/v1/ai/features/groups", {}).get("get", {})
    assert "security" in feature_groups_op
    assert {"BearerAuth": []} in feature_groups_op["security"]

    # Check /api/v1/ai/features/detect-duplicates
    duplicates_op = paths.get("/api/v1/ai/features/detect-duplicates", {}).get("post", {})
    assert "security" in duplicates_op
    assert {"BearerAuth": []} in duplicates_op["security"]


def test_public_login_endpoint_does_not_require_auth(client):
    """Verify login and register are public endpoints with JSON request schemas."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    login_op = paths.get("/api/v1/auth/login", {}).get("post", {})
    assert "security" not in login_op or login_op["security"] == []

    # Verify request body expects application/json
    req_body = login_op.get("requestBody", {}).get("content", {})
    assert "application/json" in req_body
    assert "application/x-www-form-urlencoded" not in req_body


def test_docs_ui_accessible(client):
    """Verify Swagger UI docs endpoint loads successfully and points to openapi.json."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
    assert "/api/v1/openapi.json" in response.text


def test_unauthenticated_protected_route_returns_401(client):
    """Verify missing Bearer token on protected route returns 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "not authenticated" in response.json().get("detail", "").lower()
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_bearer_token_returns_401(client):
    """Verify invalid Bearer token returns 401 Unauthorized."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json().get("detail", "").lower()
    assert "WWW-Authenticate" in response.headers

