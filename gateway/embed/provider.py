"""Embedding provider using sentence-transformers."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedder:
    """Generates embeddings using sentence-transformers models.

    Lazily loads the model on first use to avoid slow startup.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model: Any = None

    def _load_model(self) -> Any:
        """Lazy-load sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            logger.info("Loaded embedding model: %s", self._model_name)
        return self._model

    async def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.

        Returns a numpy array of shape (dimension,).
        """
        model = self._load_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return np.array(embedding, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for multiple texts.

        Returns a numpy array of shape (n_texts, dimension).
        """
        model = self._load_model()
        embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32)
        return np.array(embeddings, dtype=np.float32)

    @property
    def dimension(self) -> int:
        """Return the embedding dimension for the loaded model."""
        model = self._load_model()
        return model.get_sentence_embedding_dimension()
