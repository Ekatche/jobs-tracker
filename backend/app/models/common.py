from datetime import datetime, timezone
from typing import Any, Dict

from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


def utcnow_with_timezone():
    """Return the current UTC datetime with timezone info attached."""
    return datetime.now(timezone.utc)


class PyObjectId(str):
    """Pydantic-compatible MongoDB ObjectId string representation."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(value: Any) -> str:
            if isinstance(value, ObjectId):
                return str(value)
            if isinstance(value, str) and ObjectId.is_valid(value):
                return value
            raise ValueError(f"Invalid ObjectId: {value}")

        return core_schema.no_info_plain_validator_function(
            validate,
            metadata={"title": "ObjectId", "description": "MongoDB ObjectId"},
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, _handler: Any
    ) -> Dict[str, Any]:
        return {"type": "string", "title": "ObjectId", "description": "MongoDB ObjectId"}

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)
