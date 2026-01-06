#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Move a file within the repo.")
    parser.add_argument("--src", required=True, help="Source file path.")
    parser.add_argument("--dest", required=True, help="Destination file path.")
    parser.add_argument("--agent", required=True, help="Agent identity (required, for auditability).")
    parser.add_argument("--config", help="Optional config path override.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing destination file.",
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


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    config = load_config_with_defaults(repo_root=repo_root, config_path=args.config)
    errors = validate_config(config)
    if errors:
        raise SystemExit("Invalid config:\n- " + "\n- ".join(errors))
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
        print(f"[DRY] move {src} -> {dest}")
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    print(f"Moved: {src} -> {dest}")
    if not args.no_refresh and should_auto_refresh(config):
        refresh_dashboards(backlog_root=src_root, agent=args.agent, config_path=args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
