from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class EmbeddingTelemetry:
    """Telemetry data for an embedding operation."""
    provider_id: str
    model_name: str
    token_count: int
    dimension: int
    duration_ms: float = 0.0
    trimmed: bool = False

@dataclass(frozen=True)
class EmbeddingResult:
    """Result of an embedding operation for a single text chunk."""
    vector: List[float]
    telemetry: EmbeddingTelemetry
