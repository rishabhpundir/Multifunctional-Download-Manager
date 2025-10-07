# app/json_response.py
from typing import Any
import orjson
from fastapi.responses import ORJSONResponse
from datetime import datetime
from .datetime_utils import to_ist

def _default(obj: Any):
    if isinstance(obj, datetime):
        return to_ist(obj).isoformat()
    raise TypeError

class ISTJSONResponse(ORJSONResponse):
    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, default=_default)
