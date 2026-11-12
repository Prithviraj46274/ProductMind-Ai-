"""
ProductMind AI — MongoDB Connection Lifecycle Manager
Provides high-performance asynchronous (Motor) and synchronous (PyMongo) database access.
Maintains connection pooling, resilience, and secure credential handling.
"""

import logging
import re
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import settings

logger = logging.getLogger("productmind.database")


def sanitize_mongo_uri(uri: str) -> str:
    """Masks credentials in MongoDB connection string for safe logging."""
    if not uri:
        return ""
    try:
        return re.sub(r"//([^:]+):([^@]+)@", r"//\1:***@", uri)
    except Exception:
        return "[Protected URI]"


class MongoDBManager:
    """
    Singleton connection manager for MongoDB.
    Maintains client instances with pooled connections.
    """
    _async_client: Optional[AsyncIOMotorClient] = None
    _sync_client: Optional[MongoClient] = None
    _async_db: Optional[AsyncIOMotorDatabase] = None
    _sync_db: Optional[Database] = None

    @classmethod
    def get_database_name(cls, uri: str, fallback_name: str = "productmind_ai") -> str:
        """Extracts database name from URI path or returns fallback."""
        try:
            # Handle standard uri mongodb://.../dbname?options
            path = uri.split("?")[0].split("/")[-1]
            if path and path not in ["", "mongodb", "mongodb+srv"]:
                return path
        except Exception:
            pass
        return fallback_name

    @classmethod
    def validate_mongo_uri(cls, uri: Optional[str]) -> str:
        """
        Validates that MONGODB_URI is configured for MongoDB Atlas and never
        falls back to local MongoDB instances or unreplaced placeholders.
        """
        connection_uri = (settings.MONGODB_URI if uri is None else uri).strip()
        if not connection_uri:
            raise ValueError(
                "MONGODB_URI is not configured. Set a valid MongoDB Atlas connection string in backend/.env."
            )

        if not (connection_uri.startswith("mongodb+srv://") or connection_uri.startswith("mongodb://")):
            raise ValueError(
                "Invalid MONGODB_URI scheme. Expected a MongoDB Atlas 'mongodb+srv://' or 'mongodb://' URI."
            )

        placeholder_tokens = ("<db_username>", "<db_password>", "<username>", "<password>", "<cluster>")
        if any(token in connection_uri for token in placeholder_tokens):
            raise ValueError(
                "MONGODB_URI contains unreplaced placeholder credentials. Replace placeholders with valid Atlas credentials."
            )

        lowered = connection_uri.lower()
        local_markers = ("localhost", "127.0.0.1", "[::1]", "0.0.0.0")
        if any(marker in lowered for marker in local_markers):
            raise ValueError(
                "Local MongoDB URIs are disabled. ProductMind AI requires MongoDB Atlas exclusively."
            )

        return connection_uri

    @classmethod
    async def connect_async(cls, uri: Optional[str] = None) -> AsyncIOMotorDatabase:
        """
        Initializes or returns existing asynchronous Motor database client.
        """
        if cls._async_client is not None and cls._async_db is not None:
            return cls._async_db

        connection_uri = cls.validate_mongo_uri(uri)
        db_name = cls.get_database_name(connection_uri, settings.DATABASE_NAME)
        safe_uri = sanitize_mongo_uri(connection_uri)

        try:
            cls._async_client = AsyncIOMotorClient(
                connection_uri,
                maxPoolSize=settings.MONGO_MAX_POOL_SIZE,
                minPoolSize=settings.MONGO_MIN_POOL_SIZE,
                serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
                socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
            )
            # Verify connectivity
            await cls._async_client.admin.command("ping")
            cls._async_db = cls._async_client[db_name]
            logger.info("Connected to MongoDB Atlas (Async Motor) at %s [%s]", safe_uri, db_name)
            return cls._async_db
        except Exception as exc:
            cls._async_client = None
            cls._async_db = None
            logger.error("Failed to connect to MongoDB Atlas (Async) at %s: %s", safe_uri, exc)
            raise

    @classmethod
    def connect_sync(cls, uri: Optional[str] = None) -> Database:
        """
        Initializes or returns existing synchronous PyMongo database client.
        """
        if cls._sync_client is not None and cls._sync_db is not None:
            return cls._sync_db

        connection_uri = cls.validate_mongo_uri(uri)
        db_name = cls.get_database_name(connection_uri, settings.DATABASE_NAME)
        safe_uri = sanitize_mongo_uri(connection_uri)

        try:
            cls._sync_client = MongoClient(
                connection_uri,
                maxPoolSize=settings.MONGO_MAX_POOL_SIZE,
                minPoolSize=settings.MONGO_MIN_POOL_SIZE,
                serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
                socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
            )
            # Verify connectivity
            cls._sync_client.admin.command("ping")
            cls._sync_db = cls._sync_client[db_name]
            logger.info("Connected to MongoDB Atlas (Sync PyMongo) at %s [%s]", safe_uri, db_name)
            return cls._sync_db
        except Exception as exc:
            cls._sync_client = None
            cls._sync_db = None
            logger.error("Failed to connect to MongoDB Atlas (Sync) at %s: %s", safe_uri, exc)
            raise

    @classmethod
    async def close_async(cls) -> None:
        """Gracefully closes async Motor client."""
        if cls._async_client is not None:
            cls._async_client.close()
            cls._async_client = None
            cls._async_db = None
            logger.info("Closed MongoDB (Async Motor) connection.")

    @classmethod
    def close_sync(cls) -> None:
        """Gracefully closes sync PyMongo client."""
        if cls._sync_client is not None:
            cls._sync_client.close()
            cls._sync_client = None
            cls._sync_db = None
            logger.info("Closed MongoDB (Sync PyMongo) connection.")

    @classmethod
    def get_database(cls) -> Database:
        """Returns the active sync Database instance, initializing if necessary."""
        if cls._sync_db is None:
            return cls.connect_sync()
        return cls._sync_db

    @classmethod
    async def get_async_database(cls) -> AsyncIOMotorDatabase:
        """Returns the active async Database instance, initializing if necessary."""
        if cls._async_db is None:
            return await cls.connect_async()
        return cls._async_db


# Convenient module-level aliases
connect_to_mongo = MongoDBManager.connect_async
close_mongo_connection = MongoDBManager.close_async
get_database = MongoDBManager.get_database
get_async_database = MongoDBManager.get_async_database

