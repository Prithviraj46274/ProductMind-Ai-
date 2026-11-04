"""
ProductMind AI — MongoDB ObjectId Handling for Pydantic v2
Provides seamless serialization and deserialization between Python models and MongoDB BSON.
"""

from typing import Annotated, Any, Optional, Union
from bson import ObjectId
from pydantic import BeforeValidator, PlainSerializer
from pydantic_core import core_schema


def validate_object_id(v: Any) -> ObjectId:
    """Validates and converts string or BSON ObjectId into a valid bson.ObjectId."""
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError(f"Invalid MongoDB ObjectId: {v}")


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_object_id),
    PlainSerializer(lambda x: str(x), return_type=str, when_used="json"),
]


def to_object_id(value: Any) -> Optional[ObjectId]:
    """Safely converts an input value to ObjectId if valid, or returns None if None."""
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError(f"Invalid ObjectId string: {value}")


def to_str_id(value: Any) -> Optional[str]:
    """Safely converts an ObjectId or string to string."""
    if value is None:
        return None
    return str(value)

