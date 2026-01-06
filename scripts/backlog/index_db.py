#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import os
import traceback
from pathlib import Path

# Imports
LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit

from lib.utils import parse_frontmatter
import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)

def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Items Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            uid TEXT PRIMARY KEY,
            id TEXT,
            type TEXT,
            state TEXT,
            title TEXT,
            path TEXT UNIQUE,
            mtime REAL,
            frontmatter JSON,
            created TEXT,
            updated TEXT
        )
    """)
    
    # Indexes for speed
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_id ON items(id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_path ON items(path)")
    
    conn.commit()
    return conn

def upsert_item(conn, file_path: Path, repo_root: Path):
    try:
        content = file_path.read_text(encoding="utf-8")
        fm, _, _ = parse_frontmatter(content)
        
        if not fm:
            return False

        uid = fm.get('uid')
        if not uid:
            # Skip items without UID
            return False

        rel_path = file_path.relative_to(repo_root).as_posix()
        mtime = file_path.stat().st_mtime
        
        conn.execute("""
            INSERT OR REPLACE INTO items 
            (uid, id, type, state, title, path, mtime, frontmatter, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uid,
            fm.get('id'),
            fm.get('type'),
            fm.get('state'),
            fm.get('title'),
            rel_path,
            mtime,
            json.dumps(fm, cls=DateTimeEncoder),
            str(fm.get('created', '')),
            str(fm.get('updated', ''))
        ))
        return True
    except Exception:
        print(f"Error indexing {file_path}:")
        traceback.print_exc()
        return False

def prune_deleted(conn, repo_root: Path):
    """Remove items from DB that no longer exist on disk."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT path FROM items")
        rows = cur.fetchall()
        
        deleted_paths = []
        for (rel_path,) in rows:
            full_path = repo_root / rel_path
            if not full_path.exists():
                deleted_paths.append(rel_path)
                
        if deleted_paths:
            print(f"Pruning {len(deleted_paths)} deleted items...")
            cur.executemany("DELETE FROM items WHERE path = ?", [(p,) for p in deleted_paths])
            conn.commit()
    except sqlite3.OperationalError:
        # Table might not exist yet if init_db failed or fresh
        pass

def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize backlog items to SQLite index.")
    parser.add_argument("--backlog-root", default="_kano/backlog", help="Backlog root directory.")
    parser.add_argument("--force", action="store_true", help="Force rebuild all items (deletes DB).")
    parser.add_argument("--agent", default="system", help="Agent name (unused but keeps standard).")
    args = parser.parse_args()
    
    repo_root = Path.cwd().resolve()
    backlog_root = repo_root / args.backlog_root
    items_root = backlog_root / "items"
    
    if not items_root.exists():
        print(f"Error: Items root not found: {items_root}")
        return 1

    db_path = backlog_root / "_index" / "backlog.sqlite3"
    print(f"Syncing to index: {db_path}")
    
    if args.force and db_path.exists():
        print(f"Force: Removing existing DB {db_path}")
        try:
            os.remove(db_path)
        except OSError as e:
            print(f"Error removing DB: {e}")
            return 1
    
    conn = init_db(db_path)
    
    # 1. Prune (only if not forced/fresh)
    if not args.force:
        prune_deleted(conn, repo_root)
    
    # 2. Scan & Update
    count = 0
    updated = 0
    skipped = 0
    
    # Get existing mtimes to skip parsing
    db_mtimes = {}
    if not args.force:
        try:
            cur = conn.cursor()
            cur.execute("SELECT path, mtime FROM items")
            for row in cur.fetchall():
                db_mtimes[row[0]] = row[1]
        except sqlite3.OperationalError:
            pass
            
    try:
        for f in items_root.rglob("*.md"):
            if f.name == "README.md" or f.name.endswith(".index.md"):
                continue
                
            count += 1
            rel_path = f.relative_to(repo_root).as_posix()
            current_mtime = f.stat().st_mtime
            
            # Check if update needed
            if not args.force and rel_path in db_mtimes:
                if abs(db_mtimes[rel_path] - current_mtime) < 0.001:
                    skipped += 1
                    continue
            
            if upsert_item(conn, f, repo_root):
                updated += 1
                if updated % 10 == 0:
                    print(f"Indexed {updated} items...", end="\r")
        
        conn.commit()
    finally:
        conn.close()
    
    print(f"\nCompleted. Scanned: {count}, Updated: {updated}, Skipped: {skipped}")
    return 0

if __name__ == "__main__":
    sys.exit(run_with_audit(main))
