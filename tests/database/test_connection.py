"""
ProductMind AI — Database Connection Tests
"""

import pytest
from app.database.connection import MongoDBManager, sanitize_mongo_uri
from app.database.collections import Collections


def test_sanitize_mongo_uri():
    uri = "mongodb+srv://admin_user:SuperSecretPassword123@cluster.mongodb.net/testdb"
    sanitized = sanitize_mongo_uri(uri)
    assert "SuperSecretPassword123" not in sanitized
    assert "admin_user:***@" in sanitized


def test_sync_connection(sync_db):
    res = sync_db.command("ping")
    assert res.get("ok") == 1.0
    assert sync_db.name == "productmind_ai"


@pytest.mark.asyncio
async def test_async_connection(async_db):
    res = await async_db.command("ping")
    assert res.get("ok") == 1.0
    assert async_db.name == "productmind_ai"


@pytest.mark.asyncio
async def test_all_collections_accessible(async_db):
    existing_collections = await async_db.list_collection_names()
    for col_name in Collections.all_collections():
        assert col_name in existing_collections, f"Expected collection '{col_name}' missing from MongoDB!"

