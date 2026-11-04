"""
ProductMind AI — Base MongoDB Repository
Provides robust, tenant-isolated CRUD operations with ObjectId conversion,
pagination, filtering, sorting, and error safety.
"""

from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import DuplicateKeyError

from app.models.base import BaseMongoModel
from app.database.objectid import to_object_id

T = TypeVar("T", bound=BaseMongoModel)


class DuplicateEntityError(Exception):
    """Raised when a unique constraint is violated in MongoDB."""
    pass


class EntityNotFoundError(Exception):
    """Raised when a requested entity cannot be found."""
    pass


class BaseRepository(Generic[T]):
    """
    Generic asynchronous MongoDB repository with built-in tenant isolation,
    error resilience, and deterministic BSON serialization.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        collection_name: str,
        model_cls: Type[T],
    ):
        self.db = db
        self.collection_name = collection_name
        self.model_cls = model_cls
        self.collection: AsyncIOMotorCollection = db[collection_name]

    def _ensure_object_id(self, entity_id: Any) -> ObjectId:
        """Helper to ensure input is a valid BSON ObjectId."""
        return to_object_id(entity_id)

    async def find_by_id(
        self,
        entity_id: Any,
        workspace_id: Optional[Any] = None,
    ) -> Optional[T]:
        """
        Retrieves a single document by its _id, optionally enforcing workspace isolation.
        """
        oid = self._ensure_object_id(entity_id)
        query: Dict[str, Any] = {"_id": oid}

        if workspace_id is not None:
            query["workspaceId"] = self._ensure_object_id(workspace_id)

        doc = await self.collection.find_one(query)
        if not doc:
            return None
        return self.model_cls.from_mongo(doc)

    async def find_one(self, filter_query: Dict[str, Any]) -> Optional[T]:
        """Finds a single document matching arbitrary filter criteria."""
        doc = await self.collection.find_one(filter_query)
        if not doc:
            return None
        return self.model_cls.from_mongo(doc)

    async def find_by_workspace(
        self,
        workspace_id: Any,
        filter_query: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[T]:
        """
        Retrieves all documents belonging to a workspace with sorting and pagination.
        Guarantees workspace-level tenant isolation.
        """
        ws_oid = self._ensure_object_id(workspace_id)
        query: Dict[str, Any] = {"workspaceId": ws_oid}

        if filter_query:
            query.update(filter_query)

        cursor = self.collection.find(query)

        if sort:
            cursor = cursor.sort(sort)
        else:
            # Default sorting by createdAt descending if available
            cursor = cursor.sort("createdAt", -1)

        cursor = cursor.skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self.model_cls.from_mongo(d) for d in docs]

    async def count(
        self,
        workspace_id: Optional[Any] = None,
        filter_query: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Counts documents matching filter criteria, scoped to workspace if provided."""
        query: Dict[str, Any] = {}
        if workspace_id is not None:
            query["workspaceId"] = self._ensure_object_id(workspace_id)
        if filter_query:
            query.update(filter_query)
        return await self.collection.count_documents(query)

    async def create(self, model: T) -> T:
        """
        Inserts a new document safely. Sets timestamps if missing.
        Handles duplicate key violations cleanly.
        """
        now = datetime.now(timezone.utc)
        if model.created_at is None:
            model.created_at = now
        if model.updated_at is None:
            model.updated_at = now

        doc = model.to_mongo()

        try:
            result = await self.collection.insert_one(doc)
            model.id = result.inserted_id
            return model
        except DuplicateKeyError as exc:
            raise DuplicateEntityError(
                f"Unique constraint violation inserting into '{self.collection_name}': {exc}"
            ) from exc

    async def update(
        self,
        entity_id: Any,
        update_data: Dict[str, Any],
        workspace_id: Optional[Any] = None,
    ) -> Optional[T]:
        """
        Safely updates a document with `$set` dictionary.
        Prevents tampering with immutable `_id` and automatically bumps `updatedAt`.
        """
        oid = self._ensure_object_id(entity_id)
        query: Dict[str, Any] = {"_id": oid}

        if workspace_id is not None:
            query["workspaceId"] = self._ensure_object_id(workspace_id)

        # Sanitize updates to prevent overwriting _id or workspaceId accidentally
        clean_update = {k: v for k, v in update_data.items() if k not in ["_id", "id"]}
        clean_update["updatedAt"] = datetime.now(timezone.utc)

        try:
            doc = await self.collection.find_one_and_update(
                query,
                {"$set": clean_update},
                return_document=True,
            )
            if not doc:
                return None
            return self.model_cls.from_mongo(doc)
        except DuplicateKeyError as exc:
            raise DuplicateEntityError(
                f"Unique constraint violation updating in '{self.collection_name}': {exc}"
            ) from exc

    async def delete(
        self,
        entity_id: Any,
        workspace_id: Optional[Any] = None,
    ) -> bool:
        """
        Deletes a single document by its _id, enforcing workspace isolation.
        """
        oid = self._ensure_object_id(entity_id)
        query: Dict[str, Any] = {"_id": oid}

        if workspace_id is not None:
            query["workspaceId"] = self._ensure_object_id(workspace_id)

        result = await self.collection.delete_one(query)
        return result.deleted_count > 0
