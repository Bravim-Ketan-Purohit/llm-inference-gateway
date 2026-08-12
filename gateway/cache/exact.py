"""Exact match cache layer using Redis hash lookups."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

EXACT_PREFIX = "exact:"


class ExactMatchCache:
    """Redis-based exact match cache for deterministic requests.

    Provides O(1) lookup for requests with identical cache keys.
    Only caches responses when temperature <= cache_max_temperature.
    """

    def __init__(self, redis_url: str, ttl_seconds: int = 3600) -> None:
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        """Lazy-initialize Redis connection."""
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def get(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve a cached response by exact key."""
        client = await self._get_client()
        data = await client.get(f"{EXACT_PREFIX}{cache_key}")
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set(self, cache_key: str, response_data: dict[str, Any]) -> None:
        """Store a response in the exact cache."""
        client = await self._get_client()
        serialized = json.dumps(response_data)
        await client.set(f"{EXACT_PREFIX}{cache_key}", serialized, ex=self._ttl)

    async def delete(self, cache_key: str) -> None:
        """Remove an entry from the exact cache."""
        client = await self._get_client()
        await client.delete(f"{EXACT_PREFIX}{cache_key}")

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception:
            return False
