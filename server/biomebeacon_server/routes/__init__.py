from __future__ import annotations

from datetime import datetime

# JS numbers lose precision above 2^53, and Discord snowflakes are larger —
# the dashboard would corrupt ids, so they are serialized as strings.
_JS_SAFE_INT = 2**53


def jsonable(value):
    """Recursively converts a Mongo document into JSON-safe data."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items() if k != "_id"}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and abs(value) > _JS_SAFE_INT:
        return str(value)
    return value
