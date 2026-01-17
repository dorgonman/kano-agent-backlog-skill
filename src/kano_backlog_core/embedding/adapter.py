from abc import ABC, abstractmethod
from typing import List

from .types import EmbeddingResult

class EmbeddingAdapter(ABC):
    """Abstract base class for embedding providers."""

    def __init__(self, model_name: str):
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """
        Generate embeddings for a batch of texts.
        
        Args:
            texts: List of strings to embed.
            
        Returns:
            List of EmbeddingResult objects corresponding to input texts.
        """
        pass
