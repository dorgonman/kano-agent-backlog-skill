#!/usr/bin/env python3
"""
Hybrid Search Engine (search.py)

Combines FTS5 (full-text keyword search) with FAISS (semantic vector search).
Uses reciprocal rank fusion (RRF) to combine results.

Usage:
  python search.py --product kano-agent-backlog-skill --query "embedding chunking"
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

sys.dont_write_bytecode = True

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import faiss
except ImportError as e:
    print(f"WARNING: FAISS not available; falling back to FTS5-only search: {e}", file=sys.stderr)
    SentenceTransformer = None
    np = None
    faiss = None


def search_fts5(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
    product: Optional[str] = None,
) -> list[dict]:
    """
    Full-text search using FTS5.
    Returns: list of {chunk_id, text, score, doc_id, doc_type, title}
    """
    cursor = conn.cursor()
    
    # Build WHERE clause for product filter
    product_where = ""
    params: list = []
    
    if product:
        product_where = "AND documents.product = ?"
        params.append(product)
    
    # FTS5 search with rank scoring
    # Note: FTS5 MATCH clause must be in the WHERE condition directly
    sql = f"""
    SELECT
        chunks_fts.rowid as chunk_rowid,
        chunks.id as chunk_id,
        chunks.text,
        chunks_fts.rank as fts_score,
        chunks.doc_id,
        documents.doc_type,
        documents.title
    FROM chunks_fts
    JOIN chunks ON chunks_fts.rowid = chunks.chunk_rowid
    JOIN documents ON chunks.doc_id = documents.id
    WHERE chunks_fts MATCH ? {product_where}
    ORDER BY chunks_fts.rank ASC
    LIMIT ?
    """
    
    params.insert(0, query)
    params.append(limit)
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    results = []
    for i, row in enumerate(rows):
        results.append({
            'chunk_rowid': row['chunk_rowid'],
            'chunk_id': row['chunk_id'],
            'text': row['text'],
            'rank': i + 1,  # FTS5 rank (1-based)
            'fts_score': row['fts_score'],
            'doc_id': row['doc_id'],
            'doc_type': row['doc_type'],
            'title': row['title'],
            'method': 'fts5',
        })
    
    return results


def search_faiss(
    conn: sqlite3.Connection,
    query: str,
    model: Any,
    index: Any,
    mapping: dict,
    limit: int = 10,
    product: Optional[str] = None,
) -> list[dict]:
    """
    Semantic search using FAISS.
    Returns: list of {chunk_id, text, score, doc_id, doc_type, title}
    """
    # Encode query
    query_embedding = model.encode([query], show_progress_bar=False)[0]
    query_embedding = query_embedding.astype('float32').reshape(1, -1)
    
    # Search FAISS
    k = limit * 2  # Get more results for filtering
    distances, indices = index.search(query_embedding, k)
    
    cursor = conn.cursor()
    results = []
    
    chunk_rowids = mapping['chunk_rowids']
    chunk_ids = mapping['chunk_ids']
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0])):
        if idx < 0 or idx >= len(chunk_rowids):
            continue
        
        chunk_rowid = chunk_rowids[idx]
        chunk_id = chunk_ids[idx]
        
        # Fetch chunk metadata
        cursor.execute("""
            SELECT chunks.text, chunks.doc_id, documents.doc_type, documents.title, documents.product
            FROM chunks
            JOIN documents ON chunks.doc_id = documents.id
            WHERE chunks.chunk_rowid = ?
        """, (chunk_rowid,))
        
        row = cursor.fetchone()
        if not row:
            continue
        
        # Filter by product if needed
        if product and row[4] != product:
            continue
        
        # Normalize distance to similarity score (lower distance = higher similarity)
        # Using 1 / (1 + distance) to convert to similarity
        similarity = 1.0 / (1.0 + float(dist))
        
        results.append({
            'chunk_rowid': chunk_rowid,
            'chunk_id': chunk_id,
            'text': row[0],
            'rank': len(results) + 1,
            'distance': float(dist),
            'similarity': similarity,
            'doc_id': row[1],
            'doc_type': row[2],
            'title': row[3],
            'method': 'faiss',
        })
        
        if len(results) >= limit:
            break
    
    return results


def reciprocal_rank_fusion(
    fts_results: list[dict],
    faiss_results: list[dict],
    k: int = 60,
    fts_weight: float = 1.0,
    faiss_weight: float = 1.0,
) -> list[dict]:
    """
    Combine FTS5 and FAISS results using reciprocal rank fusion.
    Formula: score = k / (k + rank_fts) + k / (k + rank_faiss)
    """
    # Build score map by chunk_id
    scores: dict[int, dict] = {}
    
    for result in fts_results:
        chunk_id = result['chunk_id']
        if chunk_id not in scores:
            scores[chunk_id] = {
                'text': result['text'],
                'doc_id': result['doc_id'],
                'doc_type': result['doc_type'],
                'title': result['title'],
                'rrf_score': 0.0,
                'fts_rank': None,
                'faiss_rank': None,
            }
        # RRF score from FTS5 rank
        scores[chunk_id]['rrf_score'] += fts_weight * (k / (k + result['rank']))
        scores[chunk_id]['fts_rank'] = result['rank']
    
    for result in faiss_results:
        chunk_id = result['chunk_id']
        if chunk_id not in scores:
            scores[chunk_id] = {
                'text': result['text'],
                'doc_id': result['doc_id'],
                'doc_type': result['doc_type'],
                'title': result['title'],
                'rrf_score': 0.0,
                'fts_rank': None,
                'faiss_rank': None,
            }
        # RRF score from FAISS rank
        scores[chunk_id]['rrf_score'] += faiss_weight * (k / (k + result['rank']))
        scores[chunk_id]['faiss_rank'] = result['rank']
    
    # Sort by RRF score descending
    sorted_results = sorted(scores.items(), key=lambda x: x[1]['rrf_score'], reverse=True)
    
    # Return as list with final rank
    results = []
    for final_rank, (chunk_id, score_data) in enumerate(sorted_results, 1):
        results.append({
            **score_data,
            'chunk_id': chunk_id,
            'final_rank': final_rank,
        })
    
    return results


def search_hybrid(
    conn: sqlite3.Connection,
    query: str,
    model_name: str = 'all-MiniLM-L6-v2',
    index_path: Optional[Path] = None,
    mapping_path: Optional[Path] = None,
    limit: int = 10,
    product: Optional[str] = None,
) -> list[dict]:
    """
    Hybrid search: FTS5 + FAISS with RRF.
    Returns: ranked results combining both methods.
    """
    # FTS5 search (always available)
    fts_results = search_fts5(conn, query, limit, product)
    
    # FAISS search (optional)
    faiss_results = []
    if index_path and mapping_path and SentenceTransformer:
        try:
            model = SentenceTransformer(model_name)
            index = faiss.read_index(str(index_path))
            
            with open(mapping_path) as f:
                mapping = json.load(f)
            
            faiss_results = search_faiss(conn, query, model, index, mapping, limit, product)
        except Exception as e:
            print(f"WARNING: FAISS search failed: {e}", file=sys.stderr)
    
    # Combine results using RRF
    if faiss_results:
        combined = reciprocal_rank_fusion(fts_results, faiss_results)
    else:
        # Fallback: just return FTS5 results
        combined = [
            {
                **r,
                'final_rank': i + 1,
                'rrf_score': 1.0 / (1.0 + r['rank']),
                'fts_rank': r['rank'],
                'faiss_rank': None,
            }
            for i, r in enumerate(fts_results)
        ]
    
    return combined[:limit]


def main():
    parser = argparse.ArgumentParser(
        description="Hybrid search using FTS5 + FAISS."
    )
    parser.add_argument(
        '--product',
        required=True,
        help='Product name (e.g., kano-agent-backlog-skill).'
    )
    parser.add_argument(
        '--query',
        required=True,
        help='Search query.'
    )
    parser.add_argument(
        '--backlog-root',
        default='_kano/backlog',
        help='Backlog root path (default: _kano/backlog).'
    )
    parser.add_argument(
        '--db-path',
        help='SQLite DB path (optional).'
    )
    parser.add_argument(
        '--model',
        default='all-MiniLM-L6-v2',
        help='Sentence-transformers model name (default: all-MiniLM-L6-v2).'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Max results to return (default: 10).'
    )
    parser.add_argument(
        '--fts-only',
        action='store_true',
        help='Skip FAISS and use FTS5-only search.'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    backlog_root = Path(args.backlog_root).resolve()
    product_root = backlog_root / 'products' / args.product
    
    # Resolve DB path
    if args.db_path:
        db_path = Path(args.db_path).resolve()
    else:
        db_path = product_root / '_index' / 'embedding_search.db'
    
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    
    # Resolve FAISS index path
    index_path = None
    mapping_path = None
    if not args.fts_only:
        index_dir = db_path.parent / 'embeddings_faiss'
        index_file = index_dir / f"faiss_index_{args.model.replace('/', '_')}.idx"
        mapping_file = index_file.with_suffix('.mapping.json')
        
        if index_file.exists() and mapping_file.exists():
            index_path = index_file
            mapping_path = mapping_file
    
    print(f"Search Query: {args.query}")
    print(f"Product: {args.product}")
    print(f"Database: {db_path}")
    if index_path:
        print(f"FAISS Index: {index_path}")
    else:
        print("FAISS Index: (not available, using FTS5-only)")
    print()
    
    # Open database
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Perform search
    results = search_hybrid(
        conn,
        args.query,
        args.model,
        index_path,
        mapping_path,
        args.limit,
        args.product
    )
    
    conn.close()
    
    # Display results
    if not results:
        print("No results found.")
        return
    
    print(f"Found {len(results)} results:\n")
    for result in results:
        rank = result['final_rank']
        title = result['title']
        doc_type = result['doc_type']
        fts_r = f"FTS5#{result['fts_rank']}" if result['fts_rank'] else "-"
        faiss_r = f"FAISS#{result['faiss_rank']}" if result['faiss_rank'] else "-"
        rrf_score = result['rrf_score']
        
        # Truncate text
        text = result['text'][:100].replace('\n', ' ')
        
        print(f"{rank:2d}. [{doc_type:3s}] {title}")
        print(f"    Ranks: {fts_r:12s} {faiss_r:12s} | RRF: {rrf_score:.3f}")
        print(f"    Text: {text}...")
        print()


if __name__ == '__main__':
    main()
