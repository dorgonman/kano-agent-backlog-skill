#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Optional

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402


def allowed_roots_for_repo(repo_root: Path) -> List[Path]:
    return [
        (repo_root / "_kano" / "backlog").resolve(),
        (repo_root / "_kano" / "backlog_sandbox").resolve(),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy a file within the repo.")
    parser.add_argument("--src", required=True, help="Source file path.")
    parser.add_argument("--dest", required=True, help="Destination file path.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing destination file.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions only.")
    return parser.parse_args()


def resolve_path(value: str, repo_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    return path


def resolve_allowed_root(path: Path, allowed_roots: List[Path]) -> Optional[Path]:
    resolved = path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def ensure_inside_allowed(path: Path, allowed_roots: List[Path]) -> Path:
    root = resolve_allowed_root(path, allowed_roots)
    if root is None:
        allowed = " or ".join(str(root) for root in allowed_roots)
        raise SystemExit(f"Path must be inside {allowed}: {path}")
    return root


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    allowed_roots = allowed_roots_for_repo(repo_root)

    src = resolve_path(args.src, repo_root)
    dest = resolve_path(args.dest, repo_root)
    src_root = ensure_inside_allowed(src, allowed_roots)
    dest_root = ensure_inside_allowed(dest, allowed_roots)
    if src_root != dest_root:
        raise SystemExit("Source and destination must share the same root.")

    if not src.exists():
        raise SystemExit(f"Source not found: {src}")
    if not src.is_file():
        raise SystemExit(f"Source must be a file: {src}")
    if dest.exists() and not args.overwrite:
        raise SystemExit(f"Destination exists: {dest}")

    if args.dry_run:
        print(f"[DRY] copy {src} -> {dest}")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dest))
    print(f"Copied: {src} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
