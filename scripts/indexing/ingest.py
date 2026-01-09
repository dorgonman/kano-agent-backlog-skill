#!/usr/bin/env python3
"""
Embedding Database Ingester (ingest.py)

Reads chunks from TSK-0057 JSONL output and populates SQLite embedding database.
Creates documents and chunks tables, populates FTS5 index for keyword search.

Usage:
  python ingest.py --product kano-agent-backlog-skill [--jsonl-file backlog_chunks_*.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.dont_write_bytecode = True


def load_schema(schema_file: Path) -> str:
    """Load SQL schema from file."""
    try:
        return schema_file.read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"ERROR: Schema file not found: {schema_file}", file=sys.stderr)
        sys.exit(1)


def init_database(db_path: Path, schema_file: Path) -> sqlite3.Connection:
    """Initialize or open SQLite database with schema."""
    # Create parent directory if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # Apply schema
    schema = load_schema(schema_file)
    conn.executescript(schema)
    conn.commit()
    
    return conn


def ingest_jsonl(conn: sqlite3.Connection, jsonl_file: Path, product: str) -> Tuple[int, int]:
    """
    Read JSONL chunks and ingest into SQLite.
    Returns: (documents_inserted, chunks_inserted)
    """
    if not jsonl_file.exists():
        print(f"ERROR: JSONL file not found: {jsonl_file}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Ingesting {jsonl_file}")
    
    docs_cache = {}  # doc_id -> document data
    chunks_list = []
    now = datetime.now(timezone.utc).isoformat()
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk_obj = json.loads(line)
                text = chunk_obj.get('text', '')
                meta = chunk_obj.get('metadata', {})
                
                # Extract document info
                doc_id = meta.get('doc_id')
                if not doc_id:
                    print(f"WARNING: Line {line_num}: No doc_id in metadata, skipping", file=sys.stderr)
                    continue
                
                # Cache document if first time seeing this doc_id
                if doc_id not in docs_cache:
                    docs_cache[doc_id] = {
                        'id': doc_id,
                        'doc_type': meta.get('doctype', 'item'),
                        'item_type': meta.get('item_type'),
                        'title': meta.get('title', doc_id),
                        'state': meta.get('state'),
                        'product': meta.get('product', product),
                        'source_path': meta.get('source_path', ''),
                        'path_hash': meta.get('path_hash', ''),
                        'created_at': meta.get('created_at'),
                        'updated_at': meta.get('source_updated'),
                        'metadata_json': json.dumps(meta),
                    }
                
                # Build chunk record
                chunk_id = f"{doc_id}#{meta.get('section_path', '')}#{meta.get('chunk_index', 0)}"
                chunk = {
                    'id': chunk_id,
                    'doc_id': doc_id,
                    'section_path': meta.get('section_path'),
                    'chunk_kind': meta.get('chunk_kind'),
                    'chunk_index': int(meta.get('chunk_index', 0)) if meta.get('chunk_index') else 0,
                    'chunk_count': int(meta.get('chunk_count', 0)) if meta.get('chunk_count') else 0,
                    'text': text,
                    'chunk_char_len': len(text),
                    'chunk_hash': meta.get('chunk_hash', ''),
                    'worklog_span_start': meta.get('worklog_span_start'),
                    'worklog_span_end': meta.get('worklog_span_end'),
                    'language': meta.get('language', 'en'),
                    'redaction': meta.get('redaction', 'none'),
                    'schema_version': meta.get('schema_version', '0.1.0'),
                    'product': meta.get('product', product),
                }
                chunks_list.append(chunk)
                
            except json.JSONDecodeError as e:
                print(f"WARNING: Line {line_num}: Invalid JSON - {e}", file=sys.stderr)
                continue
            except Exception as e:
                print(f"WARNING: Line {line_num}: Error processing - {e}", file=sys.stderr)
                continue
    
    # Insert documents
    docs_inserted = 0
    cursor = conn.cursor()
    for doc_id, doc_data in docs_cache.items():
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO documents 
                (id, doc_type, item_type, title, state, product, source_path, path_hash, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_data['id'],
                    doc_data['doc_type'],
                    doc_data['item_type'],
                    doc_data['title'],
                    doc_data['state'],
                    doc_data['product'],
                    doc_data['source_path'],
                    doc_data['path_hash'],
                    doc_data['created_at'],
                    doc_data['updated_at'],
                    doc_data['metadata_json'],
                )
            )
            docs_inserted += 1
        except sqlite3.Error as e:
            print(f"WARNING: Could not insert document {doc_id}: {e}", file=sys.stderr)
    
    # Insert chunks
    chunks_inserted = 0
    for chunk in chunks_list:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO chunks
                (id, doc_id, section_path, chunk_kind, chunk_index, chunk_count, text, chunk_char_len, 
                 chunk_hash, worklog_span_start, worklog_span_end, language, redaction, schema_version, product)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk['id'],
                    chunk['doc_id'],
                    chunk['section_path'],
                    chunk['chunk_kind'],
                    chunk['chunk_index'],
                    chunk['chunk_count'],
                    chunk['text'],
                    chunk['chunk_char_len'],
                    chunk['chunk_hash'],
                    chunk['worklog_span_start'],
                    chunk['worklog_span_end'],
                    chunk['language'],
                    chunk['redaction'],
                    chunk['schema_version'],
                    chunk['product'],
                )
            )
            chunks_inserted += 1
        except sqlite3.Error as e:
            print(f"WARNING: Could not insert chunk {chunk['id']}: {e}", file=sys.stderr)
    
    # Update metadata
    cursor.execute(
        "UPDATE metadata SET value = ?, updated_at = ? WHERE key = 'last_ingest'",
        (now, now)
    )
    cursor.execute(
        "UPDATE metadata SET value = ?, updated_at = ? WHERE key = 'chunk_count'",
        (str(chunks_inserted), now)
    )
    
    conn.commit()
    return docs_inserted, chunks_inserted


def main():
    parser = argparse.ArgumentParser(
        description="Ingest TSK-0057 JSONL chunks into SQLite embedding database."
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
        '--jsonl-file',
        help='JSONL file path (optional; if omitted, uses latest in embeddings/ dir).'
    )
    parser.add_argument(
        '--db-path',
        help='SQLite DB path (optional; if omitted, uses default).'
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
    
    # Resolve JSONL file
    if args.jsonl_file:
        jsonl_file = Path(args.jsonl_file).resolve()
    else:
        # Find latest JSONL in embeddings directory
        embeddings_dir = product_root / '_index' / 'embeddings'
        if not embeddings_dir.exists():
            print(f"ERROR: Embeddings directory not found: {embeddings_dir}", file=sys.stderr)
            sys.exit(1)
        jsonl_files = sorted(embeddings_dir.glob('backlog_chunks_*.jsonl'))
        if not jsonl_files:
            print(f"ERROR: No JSONL files found in {embeddings_dir}", file=sys.stderr)
            sys.exit(1)
        jsonl_file = jsonl_files[-1]
    
    # Resolve schema file
    schema_file = Path(__file__).parent.parent.parent / 'references' / 'schema' / '002_embedding_search.sql'
    
    print(f"Product: {args.product}")
    print(f"JSONL file: {jsonl_file}")
    print(f"Database: {db_path}")
    
    # Initialize database
    conn = init_database(db_path, schema_file)
    print(f"✅ Database initialized")
    
    # Ingest JSONL
    docs, chunks = ingest_jsonl(conn, jsonl_file, args.product)
    print(f"✅ Ingested: {docs} documents, {chunks} chunks")
    
    # Summary
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM documents")
    total_docs = cursor.fetchone()[0]
    print(f"\n📊 Database Summary:")
    print(f"   Documents: {total_docs}")
    print(f"   Chunks: {total_chunks}")
    
    conn.close()
    print(f"\n✅ Ingest complete")


if __name__ == '__main__':
    main()
