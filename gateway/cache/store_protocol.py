"""Cache store protocol for pluggable vector backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class CacheStore(Protocol):
    """Protocol for vector similarity cache stores.

    Implementations must support storing and searching embeddings
    with associated metadata.
    """

    async def store(
        self, key: str, embedding: np.ndarray, response: str, metadata: dict[str, str]
    ) -> None:
        """Store an embedding with associated response and metadata."""
        ...

    async def search(
        self, embedding: np.ndarray, threshold: float, top_k: int = 1
    ) -> list[tuple[str, float, str]]:
        """Search for similar embeddings.

        Returns list of (key, similarity_score, response) tuples.
        """
        ...

    async def delete(self, key: str) -> None:
        """Delete an entry by key."""
        ...

    async def health_check(self) -> bool:
        """Check store connectivity."""
        ...
