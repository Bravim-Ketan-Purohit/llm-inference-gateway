"""Redis vector store using HNSW index for semantic cache."""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
import redis.asyncio as redis

logger = logging.getLogger(__name__)

INDEX_NAME = "cache_idx"
KEY_PREFIX = "cache:"


class RedisCacheStore:
    """Redis-based vector similarity store using RediSearch HNSW.

    Requires Redis Stack with the Search module enabled.
    """

    def __init__(
        self,
        redis_url: str,
        dimension: int = 384,
        distance_metric: str = "COSINE",
    ) -> None:
        self._redis_url = redis_url
        self._dimension = dimension
        self._distance_metric = distance_metric
        self._client: redis.Redis | None = None
        self._index_created = False

    async def _get_client(self) -> redis.Redis:
        """Lazy-initialize Redis connection."""
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=False)
        return self._client

    async def _ensure_index(self) -> None:
        """Create the RediSearch vector index if it doesn't exist."""
        if self._index_created:
            return

        client = await self._get_client()
        try:
            await client.execute_command("FT.INFO", INDEX_NAME)
            self._index_created = True
        except Exception:
            # Create index
            try:
                await client.execute_command(
                    "FT.CREATE",
                    INDEX_NAME,
                    "ON",
                    "HASH",
                    "PREFIX",
                    "1",
                    KEY_PREFIX,
                    "SCHEMA",
                    "embedding",
                    "VECTOR",
                    "HNSW",
                    "6",
                    "TYPE",
                    "FLOAT32",
                    "DIM",
                    str(self._dimension),
                    "DISTANCE_METRIC",
                    self._distance_metric,
                    "response",
                    "TEXT",
                    "metadata",
                    "TEXT",
                    "cache_key",
                    "TAG",
                )
                self._index_created = True
                logger.info("Created Redis vector index: %s", INDEX_NAME)
            except Exception as e:
                logger.error("Failed to create Redis index: %s", e)
                raise

    async def store(
        self, key: str, embedding: np.ndarray, response: str, metadata: dict[str, str]
    ) -> None:
        """Store an embedding with response in Redis."""
        await self._ensure_index()
        client = await self._get_client()

        embedding_bytes = embedding.astype(np.float32).tobytes()
        mapping: dict[str, Any] = {
            "embedding": embedding_bytes,
            "response": response.encode("utf-8"),
            "metadata": json.dumps(metadata).encode("utf-8"),
            "cache_key": key.encode("utf-8"),
        }
        await client.hset(f"{KEY_PREFIX}{key}", mapping=mapping)

    async def search(
        self, embedding: np.ndarray, threshold: float, top_k: int = 1
    ) -> list[tuple[str, float, str]]:
        """Search for similar embeddings using KNN."""
        await self._ensure_index()
        client = await self._get_client()

        query_embedding = embedding.astype(np.float32).tobytes()

        try:
            results = await client.execute_command(
                "FT.SEARCH",
                INDEX_NAME,
                f"*=>[KNN {top_k} @embedding $vec AS score]",
                "PARAMS",
                "2",
                "vec",
                query_embedding,
                "RETURN",
                "3",
                "score",
                "response",
                "cache_key",
                "SORTBY",
                "score",
                "DIALECT",
                "2",
            )
        except Exception as e:
            logger.warning("Redis search failed: %s", e)
            return []

        hits: list[tuple[str, float, str]] = []
        if not results or results[0] == 0:
            return hits

        # Parse results: [total_count, doc_id, [field, value, ...], ...]
        i = 1
        while i < len(results):
            _doc_id = results[i]
            fields = results[i + 1]
            i += 2

            # Parse field array into dict
            field_dict: dict[str, Any] = {}
            for j in range(0, len(fields), 2):
                k = fields[j].decode("utf-8") if isinstance(fields[j], bytes) else fields[j]
                v = fields[j + 1]
                field_dict[k] = v

            # COSINE distance: 0 = identical, 2 = opposite
            distance = float(field_dict.get("score", 2.0))
            similarity = 1.0 - distance

            if similarity >= threshold:
                resp = field_dict.get("response", b"")
                if isinstance(resp, bytes):
                    resp = resp.decode("utf-8")
                cache_key = field_dict.get("cache_key", b"")
                if isinstance(cache_key, bytes):
                    cache_key = cache_key.decode("utf-8")
                hits.append((cache_key, similarity, resp))

        return hits

    async def delete(self, key: str) -> None:
        """Delete an entry by key."""
        client = await self._get_client()
        await client.delete(f"{KEY_PREFIX}{key}")

    async def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            client = await self._get_client()
            await client.ping()
            return True
        except Exception:
            return False
