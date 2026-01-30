"""chunks_db.py - Canonical chunks SQLite DB (FTS5) operations.

This module builds a rebuildable per-product SQLite database that uses the
canonical schema (ADR-0012) and populates:
- items (metadata)
- chunks (content chunks)
- chunks_fts (FTS5 keyword search over chunks)

Source of truth remains canonical Markdown files under
_kano/backlog/products/<product>/items/**, plus ADRs and Topics.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Any
import json
import os
import sqlite3
import sys
import time

import frontmatter

from kano_backlog_core.canonical import CanonicalStore
from kano_backlog_core.chunking import chunk_text_with_tokenizer
from kano_backlog_core.chunking import ChunkingOptions
from kano_backlog_core.config import ConfigLoader
from kano_backlog_core.errors import ConfigError
from kano_backlog_core.schema import load_canonical_schema
from kano_backlog_core.tokenizer import resolve_tokenizer

from .init import _resolve_backlog_root

# Conditional import for UUIDv7
if sys.version_info >= (3, 12):
    from uuid import uuid7  # type: ignore
else:
    from uuid6 import uuid7  # type: ignore


@dataclass
class ChunksDbBuildResult:
    db_path: Path
    items_indexed: int
    chunks_indexed: int
    build_time_ms: float


@dataclass
class ChunkSearchRow:
    item_id: str
    item_title: str
    item_path: str
    chunk_id: str
    parent_uid: str
    section: Optional[str]
    content: str
    score: float


@dataclass
class ChunkFtsCandidate:
    item_id: str
    item_title: str
    item_path: str
    chunk_id: str
    parent_uid: str
    section: Optional[str]
    bm25_score: float
    snippet: str


def _scan_adrs(product_root: Path, backlog_root_path: Path) -> list[tuple[Path, Any, float]]:
    """Scan ADRs from decisions/ directory and map to canonical schema."""
    decisions_dir = product_root / "decisions"
    if not decisions_dir.exists():
        return []
    
    results = []
    for adr_path in decisions_dir.glob("ADR-*.md"):
        try:
            post = frontmatter.load(adr_path)
            adr_id = post.get("id", "")
            adr_uid = post.get("uid", "")
            
            if not adr_uid:
                adr_uid = str(uuid7())
            
            adr_title = post.get("title", adr_path.stem)
            adr_status = post.get("status", "Proposed")
            adr_date = post.get("date", "")
            
            class ADRItem:
                def __init__(self):
                    self.uid = adr_uid
                    self.id = adr_id
                    self.type = type("ItemType", (), {"value": "ADR"})()
                    self.state = type("ItemState", (), {"value": adr_status})()
                    self.title = adr_title
                    self.priority = "P3"
                    self.parent = None
                    self.owner = "system"
                    self.area = "decisions"
                    self.iteration = "backlog"
                    self.tags = []
                    self.created = str(adr_date)
                    self.updated = str(adr_date)
                    self.content = post.content
                    self.decision = post.content
            
            mtime = os.stat(adr_path).st_mtime
            results.append((adr_path, ADRItem(), mtime))
        except Exception:
            continue
    
    return results


def _scan_topics(backlog_root_path: Path) -> list[tuple[Path, Any, float]]:
    """Scan Topics from topics/ directory and map to canonical schema."""
    topics_dir = backlog_root_path / "topics"
    if not topics_dir.exists():
        return []
    
    results = []
    for topic_dir in topics_dir.iterdir():
        if not topic_dir.is_dir():
            continue
        
        manifest_path = topic_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            
            topic_name = manifest.get("topic", topic_dir.name)
            topic_uid = str(uuid7())
            topic_id = f"TOPIC-{topic_name}"
            topic_status = manifest.get("status", "open")
            topic_created = manifest.get("created_at", "")
            topic_updated = manifest.get("updated_at", "")
            
            brief_path = topic_dir / "brief.generated.md"
            brief_content = ""
            if brief_path.exists():
                brief_content = brief_path.read_text(encoding="utf-8")
            
            class TopicItem:
                def __init__(self):
                    self.uid = topic_uid
                    self.id = topic_id
                    self.type = type("ItemType", (), {"value": "Topic"})()
                    self.state = type("ItemState", (), {"value": topic_status})()
                    self.title = topic_name
                    self.priority = "P3"
                    self.parent = None
                    self.owner = manifest.get("agent", "system")
                    self.area = "topics"
                    self.iteration = "backlog"
                    self.tags = []
                    self.created = topic_created
                    self.updated = topic_updated
                    self.content = brief_content
                    self.context = brief_content
            
            mtime = os.stat(manifest_path).st_mtime
            results.append((manifest_path, TopicItem(), mtime))
        except Exception:
            continue
    
    return results


def build_chunks_db(
    *,
    product: str,
    backlog_root: Optional[Path] = None,
    force: bool = False,
) -> ChunksDbBuildResult:
    """Build the canonical chunks DB for a product."""

    t0 = time.perf_counter()

    backlog_root_path, _ = _resolve_backlog_root(backlog_root, create_if_missing=False)
    product_root = backlog_root_path / "products" / product
    # Use unified cache location: .kano/cache/backlog/
    cache_dir = backlog_root_path.parent / ".kano" / "cache" / "backlog"
    db_path = cache_dir / f"chunks.backlog.{product}.v1.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Chunks DB not found: {db_path} (run chunks build first)")

    if not query.strip():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        # FTS5 bm25(): lower is better. Convert to higher-is-better score.
        rows = cur.execute(
            """
            SELECT
                i.id,
                i.title,
                i.path,
                c.chunk_id,
                c.parent_uid,
                c.section,
                c.content,
                bm25(chunks_fts) AS bm25_score
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            JOIN items i ON i.uid = c.parent_uid
            WHERE chunks_fts MATCH ?
            ORDER BY bm25_score ASC
            LIMIT ?
            """,
            (query, int(k)),
        ).fetchall()

        out: list[ChunkSearchRow] = []
        for (
            item_id,
            item_title,
            item_path,
            chunk_id,
            parent_uid,
            section,
            content,
            bm25_score,
        ) in rows:
            score = -float(bm25_score) if bm25_score is not None else 0.0
            out.append(
                ChunkSearchRow(
                    item_id=item_id,
                    item_title=item_title,
                    item_path=item_path,
                    chunk_id=chunk_id,
                    parent_uid=parent_uid,
                    section=section,
                    content=content,
                    score=score,
                )
            )

        return out
    finally:
        conn.close()


def query_chunks_fts_candidates(
    *,
    product: str,
    query: str,
    k: int = 200,
    backlog_root: Optional[Path] = None,
    snippet_tokens: int = 20,
    snippet_prefix: str = "<mark>",
    snippet_suffix: str = "</mark>",
    snippet_ellipsis: str = "...",
) -> list[ChunkFtsCandidate]:
    """Return top-N FTS candidates with snippets for hybrid rerank."""

    backlog_root_path, _ = _resolve_backlog_root(backlog_root, create_if_missing=False)
    product_root = backlog_root_path / "products" / product
    repo_root = backlog_root_path.parent.parent
    cache_dir = repo_root / ".kano" / "cache" / "backlog"
    db_path = cache_dir / f"chunks.backlog.{product}.v1.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Chunks DB not found: {db_path} (run chunks build first)")

    if not query.strip():
        return []

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()

        rows = cur.execute(
            """
            SELECT
                i.id,
                i.title,
                i.path,
                c.chunk_id,
                c.parent_uid,
                c.section,
                bm25(chunks_fts) AS bm25_score,
                snippet(chunks_fts, 2, ?, ?, ?, ?) AS snippet
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            JOIN items i ON i.uid = c.parent_uid
            WHERE chunks_fts MATCH ?
            ORDER BY bm25_score ASC
            LIMIT ?
            """,
            (
                snippet_prefix,
                snippet_suffix,
                snippet_ellipsis,
                int(snippet_tokens),
                query,
                int(k),
            ),
        ).fetchall()

        out: list[ChunkFtsCandidate] = []
        for (
            item_id,
            item_title,
            item_path,
            chunk_id,
            parent_uid,
            section,
            bm25_score,
            snippet,
        ) in rows:
            out.append(
                ChunkFtsCandidate(
                    item_id=item_id,
                    item_title=item_title,
                    item_path=item_path,
                    chunk_id=chunk_id,
                    parent_uid=parent_uid,
                    section=section,
                    bm25_score=float(bm25_score) if bm25_score is not None else 0.0,
                    snippet=str(snippet or ""),
                )
            )

        return out
    finally:
        conn.close()
