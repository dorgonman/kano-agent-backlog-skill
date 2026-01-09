#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from config_loader import (
    allowed_roots_for_repo,
    load_config_with_defaults,
    validate_config,
)  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cleanup expired worksets from cache."
    )
    parser.add_argument(
        '--cache-root',
        default='_kano/backlog/sandboxes/.cache',
        help='Cache root (default: _kano/backlog/sandboxes/.cache).'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview cleanup without deleting.'
    )
    parser.add_argument(
        '--config',
        help='Optional config path override.'
    )
    return parser.parse_args()


def ensure_under_allowed(path: Path, allowed_roots: list[Path], label: str) -> Path:
    from config_loader import resolve_allowed_root  # noqa: E402
    root = resolve_allowed_root(path, allowed_roots)
    if root is None:
        allowed = " or ".join(str(r) for r in allowed_roots)
        raise SystemExit(f"{label} must be under {allowed}: {path}")
    return root


def is_expired(meta_path: Path) -> tuple[bool, Optional[str]]:
    """
    Check if workset is expired based on claim_until timestamp.
    Returns: (is_expired, claim_until_value)
    """
    if not meta_path.exists():
        return False, None
    
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        claim_until_str = meta.get('claim_until')
        if not claim_until_str:
            return False, None
        
        # Parse ISO format timestamp
        try:
            claim_until = datetime.fromisoformat(claim_until_str)
        except ValueError:
            # Fallback: try parsing without microseconds
            claim_until = datetime.fromisoformat(claim_until_str.split('.')[0])
        
        now = datetime.now()
        return claim_until < now, claim_until_str
    except Exception as e:
        print(f"WARNING: Failed to parse {meta_path}: {e}", file=sys.stderr)
        return False, None


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()

    config = load_config_with_defaults(repo_root=repo_root, config_path=args.config)
    errors = validate_config(config)
    if errors:
        raise SystemExit("Invalid config:\n- " + "\n- ".join(errors))

    allowed_roots = allowed_roots_for_repo(repo_root)

    cache_root = Path(args.cache_root)
    if not cache_root.is_absolute():
        cache_root = (repo_root / cache_root).resolve()
    ensure_under_allowed(cache_root, allowed_roots, "cache-root")

    if not cache_root.exists():
        print(f"Cache root not found: {cache_root}")
        return 0

    # Scan all workset directories
    expired_count = 0
    kept_count = 0
    error_count = 0

    print(f"Scanning worksets in: {cache_root.relative_to(repo_root)}")
    print()

    for ws_dir in sorted(cache_root.iterdir()):
        if not ws_dir.is_dir():
            continue
        
        meta_path = ws_dir / 'meta.json'
        expired, claim_until = is_expired(meta_path)
        
        if expired:
            item_id = "UNKNOWN"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                    item_id = meta.get('id', item_id)
                except Exception:
                    pass
            
            expired_count += 1
            print(f"[EXPIRED] {ws_dir.name} ({item_id})")
            print(f"  claim_until: {claim_until}")
            
            if not args.dry_run:
                try:
                    shutil.rmtree(ws_dir)
                    print(f"  ✓ Deleted")
                except Exception as e:
                    error_count += 1
                    print(f"  ✗ Error deleting: {e}", file=sys.stderr)
            else:
                print(f"  (would delete)")
        else:
            kept_count += 1

    print()
    print(f"Summary:")
    print(f"  Expired (eligible for cleanup): {expired_count}")
    print(f"  Active (kept): {kept_count}")
    if error_count:
        print(f"  Errors: {error_count}")
    
    if args.dry_run:
        print()
        print("DRY RUN: No changes made. Run without --dry-run to delete expired worksets.")
    
    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    raise SystemExit(run_with_audit(main))
