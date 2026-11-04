"""
ProductMind AI — Global Test Configuration & Shared Fixtures
Available across all tests (database and API).
"""

import sys
from pathlib import Path
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.database import Database

# Ensure backend package is in python path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import settings
from app.database.connection import MongoDBManager


@pytest_asyncio.fixture(scope="function")
async def async_db() -> AsyncIOMotorDatabase:
    """Function-scoped Motor async database instance ensuring proper event-loop binding."""
    MongoDBManager._async_client = None
    MongoDBManager._async_db = None
    db = await MongoDBManager.connect_async(settings.MONGODB_URI)
    yield db
    await MongoDBManager.close_async()


@pytest.fixture(scope="function")
def sync_db() -> Database:
    """PyMongo sync database instance."""
    db = MongoDBManager.connect_sync(settings.MONGODB_URI)
    yield db

