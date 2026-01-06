#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import subprocess
import shutil
import sys
from pathlib import Path
from typing import List, Optional

sys.dont_write_bytecode = True

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from config_loader import get_config_value, load_config_with_defaults, validate_config  # noqa: E402


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
    parser.add_argument("--agent", required=True, help="Agent identity (required, for auditability).")
    parser.add_argument("--config", help="Optional config path override.")
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
    parser.add_argument("--no-refresh", action="store_true", help="Disable dashboard auto-refresh.")
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


def should_auto_refresh(config: dict) -> bool:
    return bool(get_config_value(config, "views.auto_refresh", True))


def refresh_dashboards(backlog_root: Path, agent: str, config_path: Optional[str]) -> None:
    refresh_script = Path(__file__).resolve().parents[1] / "backlog" / "view_refresh_dashboards.py"
    cmd = [sys.executable, str(refresh_script), "--backlog-root", str(backlog_root), "--agent", agent]
    if config_path:
        cmd.extend(["--config", config_path])
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or "Failed to refresh dashboards.")


def permission_hint(path: Path) -> str:
    return (
        "Access denied (WinError 5). The file may be locked/open or read-only. "
        "Close any apps using it, check file attributes, or run: "
        f"python skills/kano-agent-backlog-skill/scripts/fs/diagnose_lock.py --path {path}"
    )


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    config = load_config_with_defaults(repo_root=repo_root, config_path=args.config)
    errors = validate_config(config)
    if errors:
        raise SystemExit("Invalid config:\n- " + "\n- ".join(errors))
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
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == 5:
            raise SystemExit(permission_hint(src))
        raise
    except Exception as exc:
        raise SystemExit(f"Move failed: {exc}")

    print(f"Moved to trash: {dest}")

    if args.keep:
        if not args.no_refresh and should_auto_refresh(config):
            refresh_dashboards(backlog_root=src_root, agent=args.agent, config_path=args.config)
        return 0

    try:
        dest.unlink()
        print(f"Deleted trashed copy: {dest}")
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == 5:
            print(permission_hint(dest))
        else:
            print(f"Delete failed (trash copy): {dest} ({exc})")
        print("Manual delete required for the trashed copy.")
    except Exception as exc:
        print(f"Delete failed (trash copy): {dest} ({exc})")
        print("Manual delete required for the trashed copy.")
    if not args.no_refresh and should_auto_refresh(config):
        refresh_dashboards(backlog_root=src_root, agent=args.agent, config_path=args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
