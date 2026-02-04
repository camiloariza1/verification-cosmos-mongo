from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any


def json_default(value: Any) -> Any:
    """
    JSON serializer for common MongoDB / Cosmos types.

    Keep this conservative: when unsure, fall back to str(value) so mismatch logs remain writable.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return value.hex()
    if isinstance(value, Decimal):
        return str(value)

    try:
        from bson import ObjectId  # type: ignore
        from bson.decimal128 import Decimal128  # type: ignore
    except Exception:  # pragma: no cover
        ObjectId = None  # type: ignore[assignment]
        Decimal128 = None  # type: ignore[assignment]

    if ObjectId is not None and isinstance(value, ObjectId):
        return str(value)
    if Decimal128 is not None and isinstance(value, Decimal128):
        return str(value)

    return str(value)

