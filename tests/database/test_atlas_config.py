"""Tests enforcing MongoDB Atlas exclusive configuration and zero local fallback."""

import pytest
from app.core.config import settings
from app.database.connection import MongoDBManager


def test_configured_uri_is_mongodb_atlas():
    """Verify active settings.MONGODB_URI is configured for MongoDB Atlas, not localhost."""
    validated = MongoDBManager.validate_mongo_uri(settings.MONGODB_URI)
    assert "mongodb+srv://" in validated or "mongodb.net" in validated
    assert "127.0.0.1" not in validated
    assert "localhost" not in validated.lower()


@pytest.mark.parametrize(
    "bad_uri",
    [
        "",
        "   ",
        "mongodb://127.0.0.1:27017/productmind_ai",
        "mongodb://localhost:27017/productmind_ai",
        "mongodb+srv://<db_username>:<db_password>@cluster0.o3wtc2g.mongodb.net/",
        "mongodb+srv://<username>:<password>@cluster0.example.mongodb.net/productmind_ai",
        "http://not-a-mongo-uri",
    ],
)
def test_validate_mongo_uri_rejects_local_empty_and_placeholders(bad_uri: str):
    """Verify local MongoDB URIs, empty strings, and placeholder credentials fail clearly."""
    with pytest.raises(ValueError):
        MongoDBManager.validate_mongo_uri(bad_uri)

