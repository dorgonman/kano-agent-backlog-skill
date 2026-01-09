#!/usr/bin/env python3
"""
ADR Initialization from Workset (adr_init.py)

Automatically creates ADR documents from workset notes.
Scans notes.md for Decision: markers and generates ADR stub.

Usage:
  python adr_init.py --workset <uid> --agent <agent> [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Optional

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from product_args import add_product_arguments  # noqa: E402
from config_loader import (
    allowed_roots_for_repo,
    load_config_with_defaults,
    validate_config,
)

BACKLOG_DIR = Path(__file__).resolve().parents[1] / "backlog"
if str(BACKLOG_DIR) not in sys.path:
    sys.path.insert(0, str(BACKLOG_DIR))
from lib.index import BacklogIndex  # noqa: E402


ADR_TEMPLATE = """---
id: ADR-{id}
uid: {uid}
type: Decision
title: "{title}"
state: Draft
author: {agent}
date: {date}
decision_date: {date}
status: Proposed
relates:
  - {item_id}
blocked_by: []
replaces: []
replaces_decision: []
---

# Status

Proposed

# Context

{context}

# Decision

{decision}

# Rationale

{rationale}

# Consequences

- Positive:
  - ...
- Negative:
  - ...
- Neutral:
  - ...

# Alternatives Considered

- Alternative A: ...
- Alternative B: ...

# References

- Extracted from workset for {item_id} by {agent}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create ADR from workset Decision: markers."
    )
    parser.add_argument(
        '--workset',
        required=True,
        help='Workset UID (from meta.json).'
    )
    parser.add_argument(
        '--agent',
        required=True,
        help='Agent name.'
    )
    parser.add_argument(
        '--cache-root',
        default='_kano/backlog/sandboxes/.cache',
        help='Cache root (default: _kano/backlog/sandboxes/.cache).'
    )
    parser.add_argument(
        '--backlog-root',
        default='_kano/backlog',
        help='Backlog root (default: _kano/backlog).'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview ADR without creating.'
    )
    parser.add_argument(
        '--config',
        help='Optional config path override.'
    )
    add_product_arguments(parser)
    return parser.parse_args()


def ensure_under_allowed(path: Path, allowed_roots: list[Path], label: str) -> Path:
    from config_loader import resolve_allowed_root
    root = resolve_allowed_root(path, allowed_roots)
    if root is None:
        allowed = " or ".join(str(r) for r in allowed_roots)
        raise SystemExit(f"{label} must be under {allowed}: {path}")
    return root


def extract_decision_content(notes_path: Path) -> Optional[str]:
    """
    Extract decision content from notes.md.
    Looks for lines starting with "Decision:" (case-insensitive).
    """
    if not notes_path.exists():
        return None
    
    lines = notes_path.read_text(encoding='utf-8').splitlines()
    pattern = re.compile(r'^\s*Decision\s*:\s*(.+)', re.IGNORECASE)
    
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            # Start with the actual decision text
            decision_lines = [match.group(1).strip()]
            
            # Continue to next ## header or end of file
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if next_line.startswith('##'):
                    break
                # Add non-empty lines that don't start with #
                stripped = next_line.strip()
                if stripped and not stripped.startswith('#'):
                    decision_lines.append(stripped)
            
            result = '\n'.join(decision_lines).strip()
            return result if result else None
    
    return None


def get_next_adr_number(backlog_root: Path) -> int:
    """
    Determine next ADR number by scanning existing ADRs.
    """
    decisions_dir = backlog_root / 'decisions'
    if not decisions_dir.exists():
        return 1
    
    max_num = 0
    for adr_file in decisions_dir.glob('ADR-*.md'):
        try:
            match = re.search(r'ADR-(\d+)', adr_file.name)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        except Exception:
            pass
    
    return max_num + 1


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()

    config = load_config_with_defaults(repo_root=repo_root, config_path=args.config)
    errors = validate_config(config)
    if errors:
        raise SystemExit("Invalid config:\n- " + "\n- ".join(errors))

    backlog_root = repo_root / args.backlog_root
    allowed_roots = allowed_roots_for_repo(repo_root)

    cache_root = Path(args.cache_root)
    if not cache_root.is_absolute():
        cache_root = (repo_root / cache_root).resolve()
    ensure_under_allowed(cache_root, allowed_roots, "cache-root")

    # Load workset meta
    ws_dir = cache_root / args.workset
    meta_path = ws_dir / 'meta.json'
    if not meta_path.exists():
        raise SystemExit(f"Workset meta not found: {meta_path}")
    
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception as e:
        raise SystemExit(f"Failed to read workset meta: {e}")
    
    item_id = meta.get('id', 'UNKNOWN')
    item_uid = meta.get('uid', args.workset)
    
    # Extract decision content from notes
    notes_path = ws_dir / 'notes.md'
    decision_content = extract_decision_content(notes_path)
    
    if not decision_content:
        print(f"No Decision: markers found in {notes_path.relative_to(repo_root)}")
        return 0
    
    # Determine ADR number and create filename
    adr_num = get_next_adr_number(backlog_root)
    adr_id = f"ADR-{adr_num:04d}"
    
    # Generate ADR content
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    adr_uid = f"adr-{adr_num:04d}-{item_uid[:8]}"
    
    # Extract title from decision content (first line after "Decision:")
    title_match = re.search(r'[Dd]ecision\s*:\s*(.+?)(?:\n|$)', decision_content)
    title = title_match.group(1).strip() if title_match else f"Decision for {item_id}"
    if len(title) > 80:
        title = title[:77] + "..."
    
    context = f"This decision was extracted from workset notes for task/feature {item_id}."
    decision = decision_content.replace('Decision:', '').strip()[:500]
    rationale = f"See workset notes in {ws_dir.relative_to(repo_root)} for full context."
    
    adr_content = ADR_TEMPLATE.format(
        id=f"{adr_num:04d}",
        uid=adr_uid,
        title=title,
        agent=args.agent,
        date=now,
        item_id=item_id,
        context=context,
        decision=decision,
        rationale=rationale,
    )
    
    # Determine output path
    decisions_dir = backlog_root / 'decisions'
    decisions_dir.mkdir(parents=True, exist_ok=True)
    adr_filename = f"{adr_id}_{title.lower().replace(' ', '-').replace('/', '-')}.md"
    adr_path = decisions_dir / adr_filename
    
    if args.dry_run:
        print(f"DRY RUN: Would create {adr_path.relative_to(repo_root)}")
        print()
        print(adr_content)
        return 0
    
    # Write ADR file
    adr_path.write_text(adr_content, encoding='utf-8')
    print(f"✅ Created ADR: {adr_path.relative_to(repo_root)}")
    print(f"   ID: {adr_id}")
    print(f"   Title: {title}")
    print()
    print(f"Next steps:")
    print(f"1. Review and edit: {adr_path.relative_to(repo_root)}")
    print(f"2. Link ADR back to item {item_id}:")
    print(f"   - Add '{adr_id}' to item's frontmatter 'decisions:' list")
    print(f"   - Update item's worklog: 'Created {adr_id} from workset decision'")
    
    return 0


if __name__ == '__main__':
    raise SystemExit(run_with_audit(main))
