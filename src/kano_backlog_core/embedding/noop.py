import hashlib
import time
from typing import List

from .adapter import EmbeddingAdapter
from .types import EmbeddingResult, EmbeddingTelemetry

class NoOpEmbeddingAdapter(EmbeddingAdapter):
    """
    Deterministic NoOp adapter for testing.
    Generates a pseudo-vector based on hash of input text.
    """
    
    def __init__(self, model_name: str = "noop-embedding", dimension: int = 1536):
        super().__init__(model_name)
        self._dimension = dimension

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        results = []
        for text in texts:
            # Simple deterministic pseudo-vector
            # We use sha256 of text to seed a generator-like behavior or just fill
            # predictable values. 
            # For simplicity: fill with hash bytes mod 1.0
            
            h = hashlib.sha256(text.encode("utf-8")).digest()
            # expand to dimension
            vector = []
            for i in range(self._dimension):
                # use byte at i % len(h) to generate a float -1..1
                b = h[i % len(h)]
                val = (b / 255.0) * 2 - 1
                vector.append(val)
                
            # Telemetry
            # We don't have a tokenizer here easily unless passed, 
            # so we'll just use length as a proxy or 0 for MVP noop
            token_count_est = len(text) // 4
            
            telemetry = EmbeddingTelemetry(
                provider_id="noop",
                model_name=self.model_name,
                token_count=token_count_est,
                dimension=self._dimension,
                duration_ms=0.1,
                trimmed=False
            )
            
            results.append(EmbeddingResult(vector=vector, telemetry=telemetry))
            
        return results
