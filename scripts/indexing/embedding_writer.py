#!/usr/bin/env python3
"""
Embedding Index Writer (embedding_chunking_metadata schema v0.1.0)

Transforms backlog items (.md) and ADRs into provider-agnostic JSONL chunks
following the TSK-0056 schema:
  - Per-section chunking (1200 char limit, split with 900-1100 target, 150 char overlap).
  - Worklog grouping by day (5 entries/1000 chars per chunk, 1-entry overlap).
  - Metadata: schema_version, doc_id, doctype, source_path, path_hash, section_path, chunk_hash, etc.
  - Deterministic hash-based rebuild (sha256 for path and chunk text).

Usage:
  python embedding_writer.py --product kano-agent-backlog-skill [--backlog-root _kano/backlog]
  
Output: _kano/backlog/products/<product>/_index/embeddings/backlog_chunks_<timestamp>.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from collections import defaultdict

sys.dont_write_bytecode = True

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Install with: pip install PyYAML", file=sys.stderr)
    sys.exit(1)


SCHEMA_VERSION = "0.1.0"


@dataclass
class ChunkMetadata:
    """Metadata fields for a chunk (per TSK-0056 schema)."""
    schema_version: str
    doc_id: str
    uid: Optional[str]
    doctype: str  # 'item' or 'adr'
    item_type: Optional[str]  # Task, Feature, etc. (items only)
    title: str
    state: Optional[str]
    tags: List[str]
    parent: Optional[str]
    product: str
    source_path: str
    path_hash: str
    section_path: str
    chunk_kind: str  # 'header', 'section', 'worklog', 'decision'
    chunk_index: int
    chunk_count: int
    chunk_char_len: int
    chunk_hash: str
    source_updated: Optional[str]
    created_at: Optional[str]
    worklog_span_start: Optional[str]
    worklog_span_end: Optional[str]
    language: str
    redaction: str


@dataclass
class ChunkRecord:
    """A chunk ready to emit as JSONL."""
    text: str
    metadata: ChunkMetadata

    def to_jsonl(self) -> str:
        """Serialize to JSONL line."""
        return json.dumps({
            "text": self.text,
            "metadata": asdict(self.metadata)
        })


def sha256_hash(text: str) -> str:
    """Compute sha256 hash of text, return lowercase hex."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalize_posix_path(p: Path, repo_root: Path) -> str:
    """Return POSIX-style path relative to repo_root."""
    rel = p.relative_to(repo_root)
    return rel.as_posix()


def parse_markdown_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML frontmatter from markdown.
    Expected: --- ... --- ... rest of content
    Returns: (frontmatter_dict, body_content)
    """
    if not content.startswith("---"):
        return {}, content
    
    lines = content.split("\n", 1)
    rest = lines[1] if len(lines) > 1 else ""
    
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', rest, re.DOTALL)
    if match:
        fm_text, body = match.groups()
        try:
            frontmatter = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            frontmatter = {}
        return frontmatter, body
    
    return {}, content


def extract_sections(body: str) -> Dict[str, str]:
    """
    Extract top-level sections (# Heading) from markdown body.
    Returns dict: { section_name -> section_content }
    """
    sections = {}
    current_section = "other"
    current_content = []
    
    for line in body.split("\n"):
        if line.startswith("# "):
            if current_content and current_section:
                sections[current_section] = "\n".join(current_content).strip()
            # Normalize section name: lowercase, spaces->underscores, remove non-alphanumeric except underscore
            heading = line[2:].strip().lower()
            current_section = re.sub(r'[^a-z0-9_]', '', re.sub(r'\s+', '_', heading))
            current_content = [line]
        else:
            current_content.append(line)
    
    if current_content and current_section:
        sections[current_section] = "\n".join(current_content).strip()
    
    return sections


def extract_worklog_entries(body: str) -> List[Tuple[str, str]]:
    """
    Extract worklog entries as (timestamp, text) tuples.
    Expected format in 'worklog' section:
      YYYY-MM-DD HH:MM [agent=...] ...
      YYYY-MM-DD HH:MM [agent=...] [model=...] ...
    Returns: sorted list of (timestamp, entry_text)
    """
    entries = []
    pattern = r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+\[agent=([^\]]+)\](?:\s+\[model=([^\]]+)\])?\s+(.+)$'
    
    for line in body.split("\n"):
        m = re.match(pattern, line.strip())
        if m:
            timestamp, agent, model, text = m.groups()
            # Reconstruct entry with model if present
            if model:
                full_entry = f"{timestamp} [agent={agent}] [model={model}] {text}"
            else:
                full_entry = f"{timestamp} [agent={agent}] {text}"
            entries.append((timestamp, full_entry))
    
    entries.sort(key=lambda x: x[0])
    return entries


def group_worklog_by_day(entries: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """
    Group worklog entries by calendar day (YYYY-MM-DD).
    Returns: { "YYYY-MM-DD" -> [entry_text, ...] }
    """
    by_day = defaultdict(list)
    for ts, text in entries:
        day = ts.split()[0]  # YYYY-MM-DD
        by_day[day].append(text)
    return dict(by_day)


def chunk_worklog_entries(entries_by_day: Dict[str, List[str]]) -> List[Tuple[str, str, str]]:
    """
    Split worklog entries into chunks respecting max 5 entries or 1000 chars per chunk.
    With 1-entry overlap when splitting a day.
    Returns: list of (chunk_text, span_start, span_end) tuples.
    """
    all_chunks = []
    days = sorted(entries_by_day.keys())
    
    for day in days:
        day_entries = entries_by_day[day]
        
        i = 0
        while i < len(day_entries):
            # Take up to 5 entries or until char limit
            candidate = []
            char_count = 0
            j = i
            while j < len(day_entries) and len(candidate) < 5:
                text = day_entries[j]
                if char_count + len(text) + 1 <= 1000 or not candidate:
                    candidate.append(text)
                    char_count += len(text) + 1
                    j += 1
                else:
                    break
            
            if candidate:
                chunk_text = "\n".join(candidate)
                # Extract timestamps from first and last entries
                span_start = candidate[0].split()[0:2]  # "YYYY-MM-DD HH:MM"
                span_start = " ".join(span_start) if len(span_start) == 2 else candidate[0][:19]
                span_end = candidate[-1].split()[0:2]  # "YYYY-MM-DD HH:MM"
                span_end = " ".join(span_end) if len(span_end) == 2 else candidate[-1][:19]
                all_chunks.append((chunk_text, span_start, span_end))
                # 1-entry overlap: if we didn't consume the whole day, back up 1
                i = j - 1 if j < len(day_entries) else j
            else:
                i += 1
    
    return all_chunks


def split_section_by_size(section_text: str, max_size: int = 1200, target_size: int = 1100, overlap_chars: int = 150) -> List[str]:
    """
    Split a section text into chunks if exceeds max_size.
    Target chunk size is ~target_size chars, with overlap_chars overlap between chunks.
    Splits on paragraph boundaries (\\n\\n) when possible.
    """
    if len(section_text) <= max_size:
        return [section_text]
    
    paragraphs = section_text.split("\n\n")
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para_size = len(para) + 2  # +2 for \n\n
        
        if current_size + para_size <= target_size or not current_chunk:
            current_chunk.append(para)
            current_size += para_size
        else:
            # Finalize chunk with overlap
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(chunk_text)
            
            # Start new chunk with overlap
            overlap_text = chunk_text[-overlap_chars:] if len(chunk_text) > overlap_chars else chunk_text
            current_chunk = [overlap_text, para]
            current_size = len(overlap_text) + para_size + 2
    
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    return chunks


class EmbeddingWriter:
    """Main embedding writer."""
    
    def __init__(self, product: str, backlog_root: Path, repo_root: Path):
        self.product = product
        self.backlog_root = backlog_root
        self.repo_root = repo_root
        self.product_root = backlog_root / "products" / product
        self.items_dir = self.product_root / "items"
        self.decisions_dir = self.product_root / "decisions"
        
        # Ensure output directory
        self.output_dir = self.product_root / "_index" / "embeddings"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_item(self, item_path: Path) -> Iterable[ChunkRecord]:
        """Process a single backlog item file, yield ChunkRecord chunks."""
        try:
            content = item_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"WARNING: Could not read {item_path}: {e}", file=sys.stderr)
            return
        
        # Parse frontmatter and body
        fm, body = parse_markdown_frontmatter(content)
        
        # Extract metadata
        doc_id = fm.get("id", item_path.stem)
        uid = fm.get("uid")
        item_type = fm.get("type")
        title = fm.get("title", item_path.stem)
        state = fm.get("state")
        tags = fm.get("tags", []) or []
        parent = fm.get("parent")
        source_updated = fm.get("updated")
        created_at = fm.get("created")
        
        # Normalize dates to ISO8601 if present
        if created_at:
            created_at = str(created_at)
        if source_updated:
            source_updated = str(source_updated)
        
        # Compute path hashes
        source_path = normalize_posix_path(item_path, self.repo_root)
        path_hash = sha256_hash(source_path)
        
        # Extract sections
        sections = extract_sections(body)
        
        # Emit header chunk (optional, small summary)
        header_text = f"{title}\n\n{body.split(chr(10))[0]}"  # Title + first line of body
        if header_text:
            header_meta = ChunkMetadata(
                schema_version=SCHEMA_VERSION,
                doc_id=doc_id,
                uid=uid,
                doctype="item",
                item_type=item_type,
                title=title,
                state=state,
                tags=tags,
                parent=parent,
                product=self.product,
                source_path=source_path,
                path_hash=path_hash,
                section_path="item/header",
                chunk_kind="header",
                chunk_index=0,
                chunk_count=999,  # Placeholder; will fix after counting
                chunk_char_len=len(header_text),
                chunk_hash=sha256_hash(header_text),
                source_updated=source_updated,
                created_at=created_at,
                worklog_span_start=None,
                worklog_span_end=None,
                language="en",
                redaction="none"
            )
            yield ChunkRecord(header_text, header_meta)
        
        # Emit section chunks
        section_mapping = {
            "context": "item/context",
            "goal": "item/goal",
            "approach": "item/approach",
            "acceptance_criteria": "item/acceptance_criteria",
            "risks": "item/risks",
            "non_goals": "item/non_goals",
            "decisions": "item/decisions",
            "links": "item/links",
        }
        
        section_chunks = []
        for section_name, section_text in sections.items():
            section_path = section_mapping.get(section_name, f"item/{section_name}")
            if section_text.strip():
                chunks = split_section_by_size(section_text)
                for chunk_text in chunks:
                    meta = ChunkMetadata(
                        schema_version=SCHEMA_VERSION,
                        doc_id=doc_id,
                        uid=uid,
                        doctype="item",
                        item_type=item_type,
                        title=title,
                        state=state,
                        tags=tags,
                        parent=parent,
                        product=self.product,
                        source_path=source_path,
                        path_hash=path_hash,
                        section_path=section_path,
                        chunk_kind="section",
                        chunk_index=len(section_chunks),
                        chunk_count=999,  # Placeholder
                        chunk_char_len=len(chunk_text),
                        chunk_hash=sha256_hash(chunk_text),
                        source_updated=source_updated,
                        created_at=created_at,
                        worklog_span_start=None,
                        worklog_span_end=None,
                        language="en",
                        redaction="none"
                    )
                    section_chunks.append(ChunkRecord(chunk_text, meta))
        
        for chunk in section_chunks:
            yield chunk
        
        # Emit worklog chunks if present
        if "worklog" in sections:
            worklog_text = sections["worklog"]
            entries = extract_worklog_entries(worklog_text)
            if entries:
                by_day = group_worklog_by_day(entries)
                worklog_chunks_data = chunk_worklog_entries(by_day)
                
                for idx, (chunk_text, span_start, span_end) in enumerate(worklog_chunks_data):
                    meta = ChunkMetadata(
                        schema_version=SCHEMA_VERSION,
                        doc_id=doc_id,
                        uid=uid,
                        doctype="item",
                        item_type=item_type,
                        title=title,
                        state=state,
                        tags=tags,
                        parent=parent,
                        product=self.product,
                        source_path=source_path,
                        path_hash=path_hash,
                        section_path="item/worklog",
                        chunk_kind="worklog",
                        chunk_index=idx,
                        chunk_count=len(worklog_chunks_data),
                        chunk_char_len=len(chunk_text),
                        chunk_hash=sha256_hash(chunk_text),
                        source_updated=source_updated,
                        created_at=created_at,
                        worklog_span_start=span_start,
                        worklog_span_end=span_end,
                        language="en",
                        redaction="none"
                    )
                    yield ChunkRecord(chunk_text, meta)
    
    def process_adr(self, adr_path: Path) -> Iterable[ChunkRecord]:
        """Process an ADR file, yield ChunkRecord chunks."""
        try:
            content = adr_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"WARNING: Could not read {adr_path}: {e}", file=sys.stderr)
            return
        
        # Parse frontmatter and body
        fm, body = parse_markdown_frontmatter(content)
        
        # Extract metadata
        doc_id = fm.get("id", adr_path.stem)
        uid = fm.get("uid")
        title = fm.get("title", adr_path.stem)
        state = fm.get("state")
        tags = fm.get("tags", []) or []
        source_updated = fm.get("updated")
        created_at = fm.get("created")
        
        if created_at:
            created_at = str(created_at)
        if source_updated:
            source_updated = str(source_updated)
        
        # Compute path hashes
        source_path = normalize_posix_path(adr_path, self.repo_root)
        path_hash = sha256_hash(source_path)
        
        # Extract sections
        sections = extract_sections(body)
        
        # Emit ADR section chunks
        adr_section_mapping = {
            "decision": "adr/decision",
            "context": "adr/context",
            "consequences": "adr/consequences",
            "alternatives": "adr/alternatives",
            "rationale": "adr/rationale",
            "notes": "adr/notes",
        }
        
        adr_chunks = []
        for section_name, section_text in sections.items():
            section_path = adr_section_mapping.get(section_name, f"adr/{section_name}")
            if section_text.strip():
                chunks = split_section_by_size(section_text)
                for chunk_text in chunks:
                    meta = ChunkMetadata(
                        schema_version=SCHEMA_VERSION,
                        doc_id=doc_id,
                        uid=uid,
                        doctype="adr",
                        item_type=None,
                        title=title,
                        state=state,
                        tags=tags,
                        parent=None,
                        product=self.product,
                        source_path=source_path,
                        path_hash=path_hash,
                        section_path=section_path,
                        chunk_kind="decision",
                        chunk_index=len(adr_chunks),
                        chunk_count=999,  # Placeholder
                        chunk_char_len=len(chunk_text),
                        chunk_hash=sha256_hash(chunk_text),
                        source_updated=source_updated,
                        created_at=created_at,
                        worklog_span_start=None,
                        worklog_span_end=None,
                        language="en",
                        redaction="none"
                    )
                    adr_chunks.append(ChunkRecord(chunk_text, meta))
        
        for chunk in adr_chunks:
            yield chunk
    
    def process_all(self) -> List[ChunkRecord]:
        """Process all items and ADRs, return list of all chunks."""
        all_chunks = []
        
        # Process items
        if self.items_dir.exists():
            for item_file in sorted(self.items_dir.rglob("*.md")):
                all_chunks.extend(self.process_item(item_file))
        
        # Process ADRs
        if self.decisions_dir.exists():
            for adr_file in sorted(self.decisions_dir.glob("ADR-*.md")):
                all_chunks.extend(self.process_adr(adr_file))
        
        return all_chunks
    
    def write_jsonl(self, chunks: List[ChunkRecord]) -> Path:
        """Write chunks to JSONL, return output path."""
        # Use compact ISO timestamp: YYYYMMDDTHHmmss
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        output_file = self.output_dir / f"backlog_chunks_{timestamp}.jsonl"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(chunk.to_jsonl() + "\n")
        
        return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Generate embedding chunks from backlog items and ADRs (TSK-0056 schema)."
    )
    parser.add_argument(
        "--product",
        required=True,
        help="Product name (e.g., kano-agent-backlog-skill)."
    )
    parser.add_argument(
        "--backlog-root",
        default="_kano/backlog",
        help="Backlog root path (default: _kano/backlog)."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=None,
        help="Limit to N items for testing (optional)."
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    backlog_root = Path(args.backlog_root).resolve()
    repo_root = backlog_root.parent.parent
    
    if not backlog_root.exists():
        print(f"ERROR: Backlog root not found: {backlog_root}", file=sys.stderr)
        sys.exit(1)
    
    # Run embedding writer
    print(f"Processing product: {args.product}")
    writer = EmbeddingWriter(args.product, backlog_root, repo_root)
    
    print(f"Items dir: {writer.items_dir}")
    print(f"Decisions dir: {writer.decisions_dir}")
    print(f"Output dir: {writer.output_dir}")
    
    chunks = writer.process_all()
    print(f"Generated {len(chunks)} chunks")
    
    if chunks:
        output_path = writer.write_jsonl(chunks)
        print(f"Written to: {output_path}")
    else:
        print("WARNING: No chunks generated", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
