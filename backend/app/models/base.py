"""
ProductMind AI — Base MongoDB Model
Foundation for all domain models, handling ObjectId, timestamps, and BSON serialization.
"""

from datetime import datetime, timezone
from typing import Optional, Any, Dict
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
from app.database.objectid import PyObjectId


def utc_now() -> datetime:
    """Returns current UTC timestamp in a timezone-aware manner."""
    return datetime.now(timezone.utc)


class BaseMongoModel(BaseModel):
    """
    Base model representing MongoDB document semantics.
    Supports aliased camelCase matching existing MongoDB documents,
    proper ObjectId mapping, and timestamps.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="ignore",
    )

    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")
    v: Optional[int] = Field(default=None, alias="__v")

    def to_mongo(self, exclude_unset: bool = False, exclude_none: bool = False) -> Dict[str, Any]:
        """
        Converts Pydantic model to a clean dictionary ready for MongoDB insertion/update.
        Ensures `_id` is an ObjectId if present.
        """
        data = self.model_dump(
            by_alias=True,
            exclude_unset=exclude_unset,
            exclude_none=exclude_none,
        )
        if self.id is not None:
            data["_id"] = self.id
        elif "_id" in data and data["_id"] is None:
            del data["_id"]
        return data

    @classmethod
    def from_mongo(cls, doc: Optional[Dict[str, Any]]):
        """Constructs model instance from MongoDB BSON document."""
        if not doc:
            return None
        return cls(**doc)
