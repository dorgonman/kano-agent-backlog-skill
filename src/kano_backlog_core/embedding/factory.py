from typing import Dict, Any, Optional
from .adapter import EmbeddingAdapter
from .noop import NoOpEmbeddingAdapter

def resolve_embedder(config: Dict[str, Any]) -> EmbeddingAdapter:
    """
    Resolve embedding adapter from configuration.
    
    Config schema expectation:
    {
        "provider": "noop" | "openai" | ...,
        "model": "text-embedding-3-small",
        # ... other provider specific args
    }
    """
    provider = config.get("provider", "noop")
    model_name = config.get("model", "noop-embedding")
    
    if provider == "noop":
        dimension = config.get("dimension", 1536)
        return NoOpEmbeddingAdapter(model_name=model_name, dimension=dimension)
    
    raise ValueError(f"Unknown embedding provider: {provider}")
