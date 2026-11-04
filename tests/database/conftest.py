"""
ProductMind AI — Test Configuration & Fixtures
"""

import sys
from pathlib import Path
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient

# Ensure backend package is in python path
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.database.connection import MongoDBManager


@pytest_asyncio.fixture(scope="function")
async def async_db() -> AsyncIOMotorDatabase:
    """Function-scoped Motor async database instance ensuring proper event-loop binding."""
    # Reset connection for current event loop
    MongoDBManager._async_client = None
    MongoDBManager._async_db = None
    db = await MongoDBManager.connect_async(settings.MONGODB_URI)
    yield db
    await MongoDBManager.close_async()


@pytest.fixture(scope="function")
def sync_db():
    """PyMongo sync database instance."""
    db = MongoDBManager.connect_sync(settings.MONGODB_URI)
    yield db
