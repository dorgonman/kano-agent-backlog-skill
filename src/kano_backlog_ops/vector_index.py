"""Vector indexing operations for backlog items."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import time
import logging

from kano_backlog_core.config import ConfigLoader
from kano_backlog_core.canonical import CanonicalStore
from kano_backlog_core.chunking import chunk_text, chunk_text_with_tokenizer, ChunkingOptions
from kano_backlog_core.tokenizer import resolve_model_max_tokens, resolve_tokenizer
from kano_backlog_core.token_budget import enforce_token_budget, budget_chunks
from kano_backlog_core.embedding import resolve_embedder
from kano_backlog_core.vector import VectorChunk, get_backend
from kano_backlog_core.pipeline_config import PipelineConfig

logger = logging.getLogger(__name__)

@dataclass
class VectorIndexResult:
    """Result of vector indexing operation."""
    items_processed: int
    chunks_generated: int
    chunks_indexed: int
    duration_ms: float
    backend_type: str

@dataclass
class IndexResult:
    """Result of indexing a single document."""
    chunks_count: int
    tokens_total: int
    duration_ms: float
    backend_type: str
    embedding_provider: str
    chunks_trimmed: int = 0


def index_document(
    source_id: str,
    text: str,
    config: PipelineConfig,
    *,
    product_root: Optional[Path] = None
) -> IndexResult:
    """Index a single document through the complete embedding pipeline.
    
    Args:
        source_id: Unique identifier for the document
        text: Raw text content to index
        config: Pipeline configuration with chunking, tokenizer, embedding, vector settings
        product_root: Product root directory for resolving relative paths
        
    Returns:
        IndexResult with telemetry data
        
    Raises:
        ValueError: If source_id is empty or config is invalid
        Exception: If any pipeline component fails
    """
    if not source_id:
        raise ValueError("source_id must be non-empty")
    
    if not text:
        # Handle empty text gracefully
        return IndexResult(
            chunks_count=0,
            tokens_total=0,
            duration_ms=0.0,
            backend_type=config.vector.backend,
            embedding_provider=config.embedding.provider,
            chunks_trimmed=0
        )
    
    t0 = time.perf_counter()
    
    try:
        # 1. Resolve components from config
        tokenizer = resolve_tokenizer(config.tokenizer.adapter, config.tokenizer.model)
        
        embed_cfg = {
            "provider": config.embedding.provider,
            "model": config.embedding.model,
            "dimension": config.embedding.dimension,
            **config.embedding.options
        }
        embedder = resolve_embedder(embed_cfg)
        
        # Create embedding space ID for backend isolation
        max_tokens = config.tokenizer.max_tokens or resolve_model_max_tokens(config.tokenizer.model)
        embedding_space_id = (
            f"emb:{config.embedding.provider}:{config.embedding.model}:d{config.embedding.dimension}"
            f"|tok:{config.tokenizer.adapter}:{config.tokenizer.model}:max{max_tokens}"
            f"|chunk:{config.chunking.version}"
            f"|metric:{config.vector.metric}"
        )
        
        # Resolve vector path
        vec_path = Path(config.vector.path)
        if not vec_path.is_absolute() and product_root:
            vec_path = product_root / vec_path
        
        vec_cfg = {
            "backend": config.vector.backend,
            "path": str(vec_path),
            "collection": config.vector.collection,
            "embedding_space_id": embedding_space_id,
            **config.vector.options
        }
        backend = get_backend(vec_cfg)
        backend.prepare(schema={}, dims=config.embedding.dimension, metric=config.vector.metric)
        
        # 2. Chunk the text using enhanced chunking with tokenizer integration
        # Use the new chunk_text_with_tokenizer for better accuracy
        raw_chunks = chunk_text_with_tokenizer(
            source_id=source_id,
            text=text,
            options=config.chunking,
            tokenizer=tokenizer,
            model_name=config.tokenizer.model
        )
        
        if not raw_chunks:
            return IndexResult(
                chunks_count=0,
                tokens_total=0,
                duration_ms=(time.perf_counter() - t0) * 1000,
                backend_type=config.vector.backend,
                embedding_provider=config.embedding.provider,
                chunks_trimmed=0
            )
        
        # 3. Apply token budgeting to each chunk
        budgeted_chunks = []
        for chunk in raw_chunks:
            budgeted = enforce_token_budget(
                chunk.text,
                tokenizer,
                max_tokens=max_tokens
            )
            budgeted_chunks.append(budgeted)
        
        # 4. Prepare chunks for embedding
        chunk_texts = [budgeted.content for budgeted in budgeted_chunks]
        
        # 5. Generate embeddings
        embedding_results = embedder.embed_batch(chunk_texts)
        
        # 6. Create VectorChunk objects and upsert to backend
        chunks_indexed = 0
        tokens_total = 0
        chunks_trimmed = 0
        
        for i, (raw_chunk, budgeted, embedding_result) in enumerate(zip(raw_chunks, budgeted_chunks, embedding_results)):
            tokens_total += budgeted.token_count.count
            if budgeted.trimmed:
                chunks_trimmed += 1
                
            vector_chunk = VectorChunk(
                chunk_id=raw_chunk.chunk_id,
                text=budgeted.content,
                metadata={
                    "source_id": source_id,
                    "start_char": raw_chunk.start_char,
                    "end_char": raw_chunk.end_char,
                    "trimmed": budgeted.trimmed,
                    "token_count": budgeted.token_count.count,
                    "token_count_method": budgeted.token_count.method,
                    "tokenizer_id": budgeted.token_count.tokenizer_id,
                    "is_exact": budgeted.token_count.is_exact,
                    "target_budget": budgeted.target_budget,
                    "safety_margin": budgeted.safety_margin,
                    "embedding_provider": config.embedding.provider,
                    "embedding_model": config.embedding.model,
                    "embedding_dimension": config.embedding.dimension,
                    "chunking_method": "tokenizer_aware",  # New telemetry field
                    "tokenizer_adapter": config.chunking.tokenizer_adapter,  # New telemetry field
                },
                vector=embedding_result.vector
            )
            
            backend.upsert(vector_chunk)
            chunks_indexed += 1
        
        # 6. Persist changes
        backend.persist()
        
        duration_ms = (time.perf_counter() - t0) * 1000
        
        return IndexResult(
            chunks_count=chunks_indexed,
            tokens_total=tokens_total,
            duration_ms=duration_ms,
            backend_type=config.vector.backend,
            embedding_provider=config.embedding.provider,
            chunks_trimmed=chunks_trimmed
        )
        
    except Exception as e:
        logger.error(f"Failed to index document {source_id}: {e}")
        raise

def build_vector_index(
    *,
    product: str,
    backlog_root: Optional[Path] = None,
    force: bool = False
) -> VectorIndexResult:
    """Build vector index for a product."""
    t0 = time.perf_counter()
    
    # Load config
    resource_path = backlog_root or Path(".")
    ctx, effective = ConfigLoader.load_effective_config(
        resource_path,
        product=product
    )
    
    pc = ConfigLoader.validate_pipeline_config(effective)
    
    # Resolve components
    tokenizer = resolve_tokenizer(pc.tokenizer.adapter, pc.tokenizer.model)
    
    embed_cfg = {
        "provider": pc.embedding.provider,
        "model": pc.embedding.model,
        "dimension": pc.embedding.dimension,
    }
    embedder = resolve_embedder(embed_cfg)
    
    vec_path = Path(pc.vector.path)
    if not vec_path.is_absolute():
        vec_path = ctx.product_root / vec_path
        
    embedding_space_id = (
        f"emb:{pc.embedding.provider}:{pc.embedding.model}:d{pc.embedding.dimension}"
        f"|tok:{pc.tokenizer.adapter}:{pc.tokenizer.model}:max{pc.tokenizer.max_tokens or resolve_model_max_tokens(pc.tokenizer.model)}"
        f"|chunk:{pc.chunking.version}"
        f"|metric:{pc.vector.metric}"
    )

    vec_cfg = {
        "backend": pc.vector.backend,
        "path": str(vec_path),
        "collection": pc.vector.collection,
        "embedding_space_id": embedding_space_id,
    }
    backend = get_backend(vec_cfg)
    backend.prepare(schema={}, dims=pc.embedding.dimension, metric=pc.vector.metric)
    
    # Process items
    store = CanonicalStore(ctx.product_root)
    items_processed = 0
    chunks_generated = 0
    chunks_indexed = 0
    
    current_batch = []
    BATCH_SIZE = 16
    
    def flush_batch():
        nonlocal current_batch, chunks_indexed
        if not current_batch:
            return
        texts = [c.text for c in current_batch]
        embeddings = embedder.embed_batch(texts)
        for i, res in enumerate(embeddings):
            chunk = current_batch[i]
            chunk.vector = res.vector
            backend.upsert(chunk)
            chunks_indexed += 1
        current_batch = []

    for path in store.list_items():
        try:
            item = store.read(path)
            items_processed += 1
            
            # Construct text from item fields
            text_parts = [item.title]
            
            # Add structured content sections
            if item.context:
                text_parts.append(f"Context: {item.context}")
            if item.goal:
                text_parts.append(f"Goal: {item.goal}")
            if item.approach:
                text_parts.append(f"Approach: {item.approach}")
            if item.acceptance_criteria:
                text_parts.append(f"Acceptance Criteria: {item.acceptance_criteria}")
            if item.risks:
                text_parts.append(f"Risks: {item.risks}")
            if item.non_goals:
                text_parts.append(f"Non-Goals: {item.non_goals}")
            if item.alternatives:
                text_parts.append(f"Alternatives: {item.alternatives}")
            
            text_to_chunk = "\n\n".join(text_parts)
            
            raw_chunks = chunk_text_with_tokenizer(
                source_id=item.id,
                text=text_to_chunk,
                options=pc.chunking,
                tokenizer=tokenizer,
                model_name=pc.tokenizer.model
            )

            for rc in raw_chunks:
                max_tokens = pc.tokenizer.max_tokens or resolve_model_max_tokens(
                    pc.tokenizer.model
                )
                budget_res = enforce_token_budget(rc.text, tokenizer, max_tokens=max_tokens)

                vc = VectorChunk(
                    chunk_id=rc.chunk_id,
                    text=budget_res.content,
                    metadata={
                        "source_id": item.id,
                        "start_char": rc.start_char,
                        "end_char": rc.end_char,
                        "trimmed": budget_res.trimmed,
                        "token_count": budget_res.token_count.count,
                        "token_count_method": budget_res.token_count.method,
                        "tokenizer_id": budget_res.token_count.tokenizer_id,
                        "is_exact": budget_res.token_count.is_exact,
                        "target_budget": budget_res.target_budget,
                        "safety_margin": budget_res.safety_margin,
                        "max_tokens": max_tokens,
                    },
                )

                current_batch.append(vc)
                chunks_generated += 1

                if len(current_batch) >= BATCH_SIZE:
                    flush_batch()
                    
        except Exception as e:
            logger.warning(f"Failed to process {path}: {e}")
            continue

    flush_batch()
    backend.persist()
    
    duration = (time.perf_counter() - t0) * 1000
    return VectorIndexResult(
        items_processed=items_processed,
        chunks_generated=chunks_generated,
        chunks_indexed=chunks_indexed,
        duration_ms=duration,
        backend_type=pc.vector.backend
    )
