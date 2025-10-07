# app/datetime_utils.py
from __future__ import annotations
from datetime import datetime
from .timezone import IST, UTC

def utcnow() -> datetime:
    # Always use aware UTC
    return datetime.now(UTC)

def now_ist() -> datetime:
    return datetime.now(IST)

def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # assume UTC if naive arrives from DB
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # if a naive timestamp arrives from client, treat as IST
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(UTC)
