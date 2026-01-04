#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
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
    parser = argparse.ArgumentParser(
        description="Move a file into a trash bin, then optionally delete it."
    )
    parser.add_argument("--path", required=True, help="File path to trash.")
    parser.add_argument(
        "--trash-root",
        default="_kano/backlog/_trash",
        help="Trash root (default: _kano/backlog/_trash).",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the trashed copy (skip delete attempt).",
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

    src = resolve_path(args.path, repo_root)
    src_root = ensure_inside_allowed(src, allowed_roots)

    if not src.exists():
        raise SystemExit(f"Path not found: {src}")
    if not src.is_file():
        raise SystemExit(f"Only files are supported: {src}")

    trash_root = resolve_path(args.trash_root, repo_root)
    trash_root_root = ensure_inside_allowed(trash_root, allowed_roots)
    if trash_root_root != src_root:
        raise SystemExit("Trash root must share the same root as the source file.")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = trash_root / stamp / src.relative_to(repo_root)

    if args.dry_run:
        print(f"[DRY] move {src} -> {dest}")
        print("[DRY] delete trashed copy (unless --keep)")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(src), str(dest))
    except Exception as exc:
        raise SystemExit(f"Move failed: {exc}")

    print(f"Moved to trash: {dest}")

    if args.keep:
        return 0

    try:
        dest.unlink()
        print(f"Deleted trashed copy: {dest}")
    except Exception as exc:
        print(f"Delete failed (trash copy): {dest} ({exc})")
        print("Manual delete required for the trashed copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
