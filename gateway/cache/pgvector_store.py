"""PGVector store for semantic cache with pgvector extension."""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class PgvectorCacheStore:
    """PostgreSQL-based vector similarity store using pgvector.

    Uses cosine similarity for nearest-neighbor search.
    """

    def __init__(self, dsn: str, dimension: int = 384) -> None:
        self._dsn = dsn
        self._dimension = dimension
        self._pool: Any = None

    async def _get_pool(self) -> Any:
        """Lazy-initialize connection pool."""
        if self._pool is None:
            import psycopg_pool

            self._pool = psycopg_pool.AsyncConnectionPool(self._dsn, min_size=2, max_size=10)
            await self._pool.open()
        return self._pool

    async def store(
        self, key: str, embedding: np.ndarray, response: str, metadata: dict[str, str]
    ) -> None:
        """Store an embedding with response in PostgreSQL."""
        pool = await self._get_pool()
        embedding_list = embedding.tolist()
        meta_json = json.dumps(metadata)

        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO semantic_cache (cache_key, embedding, response, metadata)
                VALUES (%s, %s::vector, %s, %s::jsonb)
                ON CONFLICT (cache_key) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    response = EXCLUDED.response,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                (key, str(embedding_list), response, meta_json),
            )

    async def search(
        self, embedding: np.ndarray, threshold: float, top_k: int = 1
    ) -> list[tuple[str, float, str]]:
        """Search for similar embeddings using cosine distance."""
        pool = await self._get_pool()
        embedding_list = embedding.tolist()

        async with pool.connection() as conn:
            rows = await conn.execute(
                """
                SELECT cache_key, 1 - (embedding <=> %s::vector) AS similarity, response
                FROM semantic_cache
                WHERE 1 - (embedding <=> %s::vector) >= %s
                ORDER BY similarity DESC
                LIMIT %s
                """,
                (str(embedding_list), str(embedding_list), threshold, top_k),
            )
            results = await rows.fetchall()

        return [(row[0], float(row[1]), row[2]) for row in results]

    async def delete(self, key: str) -> None:
        """Delete an entry by key."""
        pool = await self._get_pool()
        async with pool.connection() as conn:
            await conn.execute("DELETE FROM semantic_cache WHERE cache_key = %s", (key,))

    async def health_check(self) -> bool:
        """Check PostgreSQL connectivity."""
        try:
            pool = await self._get_pool()
            async with pool.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            return False
