"""Correlation identifier for one collection query, propagated to worker threads."""

from contextvars import ContextVar
from hashlib import sha256

collection_query_id: ContextVar[str | None] = ContextVar("collection_query_id", default=None)


def query_fingerprint(query: str) -> str:
    return sha256(query.strip().casefold().encode()).hexdigest()[:16]
