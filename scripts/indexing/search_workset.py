#!/usr/bin/env python3
"""
Workset-scoped Search (search_workset.py)

Convenience wrapper for searching within a workset's scope using hybrid search.
Automatically resolves the workset's item and restricts results to that scope.

Usage:
  python search_workset.py --workset <uid> --query "embedding chunking" [--limit 5] [--fts-only]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search within workset scope using hybrid FTS5 + FAISS."
    )
    parser.add_argument(
        '--workset',
        required=True,
        help='Workset UID (required).'
    )
    parser.add_argument(
        '--query',
        required=True,
        help='Search query.'
    )
    parser.add_argument(
        '--product',
        default='kano-agent-backlog-skill',
        help='Product name (default: kano-agent-backlog-skill).'
    )
    parser.add_argument(
        '--backlog-root',
        default='_kano/backlog',
        help='Backlog root path (default: _kano/backlog).'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Max results to return (default: 5).'
    )
    parser.add_argument(
        '--fts-only',
        action='store_true',
        help='Skip FAISS and use FTS5-only search.'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print debug info.'
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    backlog_root = repo_root / args.backlog_root
    
    # Resolve workset meta to get item id
    ws_meta_path = backlog_root / 'sandboxes' / '.cache' / args.workset / 'meta.json'
    if not ws_meta_path.exists():
        print(f"ERROR: Workset meta not found: {ws_meta_path}", file=sys.stderr)
        return 1
    
    try:
        ws_meta = json.loads(ws_meta_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"ERROR: Failed to read workset meta: {e}", file=sys.stderr)
        return 1
    
    item_id = ws_meta.get('id')
    if not item_id:
        print("ERROR: Workset meta missing 'id' field", file=sys.stderr)
        return 1
    
    if args.verbose:
        print(f"Workset UID: {args.workset}")
        print(f"Item ID: {item_id}")
    
    # Build search.py command
    search_script = Path(__file__).resolve().parent / 'search.py'
    cmd = [
        sys.executable,
        str(search_script),
        '--product', args.product,
        '--query', args.query,
        '--backlog-root', args.backlog_root,
        '--limit', str(args.limit),
        '--workset', args.workset,  # Pass workset directly to search.py
    ]
    
    if args.fts_only:
        cmd.append('--fts-only')
    
    if args.verbose:
        print(f"Executing: {' '.join(cmd)}")
        print()
    
    # Execute search
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
