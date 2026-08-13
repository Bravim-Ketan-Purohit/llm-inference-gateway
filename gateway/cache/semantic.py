"""Semantic cache manager combining exact and vector similarity layers."""

from __future__ import annotations

import logging
from typing import Any

from gateway.cache.exact import ExactMatchCache
from gateway.cache.keys import canonical_cache_key
from gateway.cache.store_protocol import CacheStore

logger = logging.getLogger(__name__)


class SemanticCache:
    """Two-layer cache: exact match first, then semantic similarity.

    1. Exact layer: O(1) Redis lookup by canonical cache key
    2. Semantic layer: Vector similarity search (Redis HNSW or pgvector)
    """

    def __init__(
        self,
        exact_cache: ExactMatchCache,
        vector_store: CacheStore,
        embedder: Any,
        threshold: float = 0.92,
        max_temperature: float = 0.2,
    ) -> None:
        self._exact = exact_cache
        self._vector = vector_store
        self._embedder = embedder
        self._threshold = threshold
        self._max_temperature = max_temperature

    async def lookup(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: str | list[str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        tenant_id: str | None = None,
    ) -> tuple[str | None, str]:
        """Look up a cached response.

        Returns (cached_response_or_None, cache_key).
        """
        # Skip cache if temperature is too high for deterministic results
        effective_temp = temperature if temperature is not None else 0.0

        cache_key = canonical_cache_key(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=stop,
            tools=tools,
            response_format=response_format,
            tenant_id=tenant_id,
        )

        # Layer 1: Exact match
        if effective_temp <= self._max_temperature:
            exact_hit = await self._exact.get(cache_key)
            if exact_hit is not None:
                logger.debug("Exact cache hit for key=%s", cache_key[:16])
                return exact_hit.get("content", ""), cache_key

        # Layer 2: Semantic similarity
        user_content = " ".join(
            m.get("content", "") for m in messages if m.get("role") in ("user", "assistant")
        )
        if not user_content.strip():
            return None, cache_key

        embedding = await self._embedder.embed(user_content)
        results = await self._vector.search(
            embedding=embedding, threshold=self._threshold, top_k=1
        )

        if results:
            hit_key, similarity, response = results[0]
            logger.debug(
                "Semantic cache hit: similarity=%.4f key=%s", similarity, hit_key[:16]
            )
            return response, cache_key

        return None, cache_key

    async def store(
        self,
        *,
        cache_key: str,
        messages: list[dict[str, Any]],
        response_content: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Store a response in both cache layers."""
        # Store in exact cache
        await self._exact.set(cache_key, {"content": response_content})

        # Store in vector store
        user_content = " ".join(
            m.get("content", "") for m in messages if m.get("role") in ("user", "assistant")
        )
        if user_content.strip():
            embedding = await self._embedder.embed(user_content)
            await self._vector.store(
                key=cache_key,
                embedding=embedding,
                response=response_content,
                metadata=metadata or {},
            )
