"""
ProductMind AI — FastAPI Setup & Health Endpoint Tests
Phase 2, Step 1 Verification.
"""

import sys
import os
from fastapi.testclient import TestClient

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_root_endpoint():
    """Verify root discovery endpoint returns service metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "ProductMind AI"
    assert data["version"] == "1.0.0"
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/v1/health"


def test_health_endpoint():
    """Verify GET /api/v1/health returns HTTP 200 with operational status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ProductMind AI"
    assert data["version"] == "1.0.0"
    assert "timestamp" in data


def test_openapi_json_accessible():
    """Verify OpenAPI specification is accessible and has accurate metadata."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "ProductMind AI"
    assert schema["info"]["version"] == "1.0.0"
    assert "/api/v1/health" in schema["paths"]


def test_swagger_docs_accessible():
    """Verify Swagger UI documentation is accessible at /docs."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SwaggerUIBundle" in response.text


def test_cors_middleware_configured():
    """Verify CORS headers respond to configured origins."""
    test_origin = "http://localhost:5173"
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": test_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == test_origin
