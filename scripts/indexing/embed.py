#!/usr/bin/env python3
"""
Embedding Generator (embed.py)

Generates embeddings for chunks using sentence-transformers.
Stores embeddings in FAISS index for fast nearest-neighbor search.

Usage:
  python embed.py --product kano-agent-backlog-skill [--model all-MiniLM-L6-v2]
"""

from __future__ import annotations

import argparse
import json
import pickle
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.dont_write_bytecode = True

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import faiss
except ImportError as e:
    print(f"ERROR: Required libraries not installed: {e}", file=sys.stderr)
    print("Install with: pip install sentence-transformers numpy faiss-cpu", file=sys.stderr)
    sys.exit(1)


def embed_chunks(
    conn: sqlite3.Connection,
    model_name: str = 'all-MiniLM-L6-v2',
    batch_size: int = 32,
) -> tuple[int, int]:
    """
    Generate embeddings for chunks without embedding_generated flag set.
    Returns: (processed, skipped)
    """
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)
    embedding_dim = model.get_sentence_embedding_dimension()
    print(f"✅ Model loaded (embedding dimension: {embedding_dim})")
    
    # Fetch chunks needing embeddings
    cursor = conn.cursor()
    cursor.execute("SELECT id, text FROM chunks WHERE embedding_generated = 0 LIMIT ?", (batch_size * 100,))
    rows = cursor.fetchall()
    
    if not rows:
        print("No chunks needing embeddings")
        return 0, 0
    
    print(f"Processing {len(rows)} chunks")
    
    # Generate embeddings
    texts = [row[1] for row in rows]
    chunk_ids = [row[0] for row in rows]
    
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=batch_size)
    
    print(f"✅ Generated {len(embeddings)} embeddings")
    
    # Mark chunks as processed (for future: would store embeddings in FAISS index)
    processed = 0
    for chunk_id in chunk_ids:
        try:
            cursor.execute(
                "UPDATE chunks SET embedding_generated = 1 WHERE id = ?",
                (chunk_id,)
            )
            processed += 1
        except sqlite3.Error as e:
            print(f"WARNING: Could not mark chunk {chunk_id}: {e}", file=sys.stderr)
    
    # Update metadata
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "UPDATE metadata SET value = ?, updated_at = ? WHERE key = 'last_embed'",
        (now, now)
    )
    
    conn.commit()
    return processed, len(rows) - processed


def build_faiss_index(
    conn: sqlite3.Connection,
    model_name: str = 'all-MiniLM-L6-v2',
    index_file: Optional[Path] = None,
    batch_size: int = 32,
) -> Path:
    """
    Build FAISS index from all chunks.
    Returns: path to saved index file
    """
    if index_file is None:
        raise ValueError("index_file path required")
    
    print(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)
    embedding_dim = model.get_sentence_embedding_dimension()
    
    # Fetch all chunks
    cursor = conn.cursor()
    cursor.execute("SELECT chunk_rowid, id, text FROM chunks ORDER BY chunk_rowid")
    rows = cursor.fetchall()
    
    if not rows:
        print("ERROR: No chunks to embed", file=sys.stderr)
        sys.exit(1)
    
    print(f"Embedding {len(rows)} chunks")
    texts = [row[2] for row in rows]
    chunk_rowids = [row[0] for row in rows]
    chunk_ids = [row[1] for row in rows]
    
    # Generate embeddings
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=batch_size)
    embeddings = embeddings.astype('float32')
    
    print(f"✅ Generated embeddings shape: {embeddings.shape}")
    
    # Build FAISS index
    print("Building FAISS index...")
    index = faiss.IndexFlatL2(embedding_dim)  # L2 (Euclidean) distance
    index.add(embeddings)
    
    # Save index and chunk ID mapping
    faiss.write_index(index, str(index_file))
    
    # Save chunk ID mapping (rowids + chunk ids)
    mapping_file = index_file.with_suffix('.mapping.json')
    with open(mapping_file, 'w') as f:
        json.dump({'chunk_rowids': chunk_rowids, 'chunk_ids': chunk_ids}, f)
    
    print(f"✅ FAISS index saved: {index_file}")
    print(f"✅ Chunk ID mapping saved: {mapping_file}")
    
    # Update metadata
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        "UPDATE metadata SET value = ?, updated_at = ? WHERE key = 'faiss_index_size'",
        (str(index.ntotal), now)
    )
    cursor.execute(
        "UPDATE metadata SET value = ?, updated_at = ? WHERE key = 'last_embed'",
        (now, now)
    )
    conn.commit()
    
    return index_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for chunks and build FAISS index."
    )
    parser.add_argument(
        '--product',
        required=True,
        help='Product name (e.g., kano-agent-backlog-skill).'
    )
    parser.add_argument(
        '--backlog-root',
        default='_kano/backlog',
        help='Backlog root path (default: _kano/backlog).'
    )
    parser.add_argument(
        '--model',
        default='all-MiniLM-L6-v2',
        help='Sentence-transformers model name (default: all-MiniLM-L6-v2).'
    )
    parser.add_argument(
        '--db-path',
        help='SQLite DB path (optional; if omitted, uses default).'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=32,
        help='Embedding generation batch size (default: 32).'
    )
    parser.add_argument(
        '--skip-faiss',
        action='store_true',
        help='Skip FAISS index building (just mark chunks as processed).'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    backlog_root = Path(args.backlog_root).resolve()
    product_root = backlog_root / 'products' / args.product
    
    if not backlog_root.exists():
        print(f"ERROR: Backlog root not found: {backlog_root}", file=sys.stderr)
        sys.exit(1)
    
    # Resolve DB path
    if args.db_path:
        db_path = Path(args.db_path).resolve()
    else:
        db_path = product_root / '_index' / 'embedding_search.db'
    
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        print(f"       Run ingest.py first to create the database", file=sys.stderr)
        sys.exit(1)
    
    # Resolve FAISS index path
    index_dir = db_path.parent / 'embeddings_faiss'
    index_dir.mkdir(parents=True, exist_ok=True)
    index_file = index_dir / f"faiss_index_{args.model.replace('/', '_')}.idx"
    
    print(f"Product: {args.product}")
    print(f"Database: {db_path}")
    print(f"Model: {args.model}")
    print(f"FAISS index: {index_file}")
    
    # Open database
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Build FAISS index
    if not args.skip_faiss:
        build_faiss_index(conn, args.model, index_file, args.batch_size)
    else:
        print("Skipping FAISS index building")
        # Just mark chunks as processed
        cursor = conn.cursor()
        cursor.execute("UPDATE chunks SET embedding_generated = 1 WHERE embedding_generated = 0")
        conn.commit()
        print(f"✅ Marked chunks as processed")
    
    conn.close()
    print(f"\n✅ Embedding generation complete")


if __name__ == '__main__':
    main()
