#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.dont_write_bytecode = True

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show kano-agent-backlog-skill version information.")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent identity running the script (required, used for auditability).",
    )
    return parser.parse_args()


def _skill_root() -> Path:
    # <skill-root>/scripts/backlog/version_show.py
    return Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _resolve_gitdir(skill_root: Path) -> Optional[Path]:
    dotgit = skill_root / ".git"
    if dotgit.is_dir():
        return dotgit
    if dotgit.is_file():
        text = _read_text(dotgit)
        if not text:
            return None
        prefix = "gitdir:"
        if not text.lower().startswith(prefix):
            return None
        raw = text[len(prefix) :].strip()
        gitdir = Path(raw)
        if not gitdir.is_absolute():
            gitdir = (skill_root / gitdir).resolve()
        return gitdir if gitdir.exists() else None
    return None


def _read_head_commit(gitdir: Path) -> Optional[str]:
    head = _read_text(gitdir / "HEAD")
    if not head:
        return None
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        ref_path = gitdir / ref
        commit = _read_text(ref_path)
        if commit:
            return commit
        packed = _read_text(gitdir / "packed-refs")
        if not packed:
            return None
        for line in packed.splitlines():
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            sha, name = line.split(" ", 1)
            if name.strip() == ref:
                return sha.strip()
        return None
    return head.strip()


def _load_version_info() -> Dict[str, Any]:
    root = _skill_root()
    version = _read_text(root / "VERSION") or "0.0.0+unknown"
    changelog = (root / "CHANGELOG.md").as_posix()
    versioning = (root / "VERSIONING.md").as_posix()

    gitdir = _resolve_gitdir(root)
    commit = _read_head_commit(gitdir) if gitdir else None

    return {
        "name": "kano-agent-backlog-skill",
        "version": version,
        "path": str(root),
        "changelog": changelog,
        "versioning": versioning,
        "commit": commit,
    }


def main() -> int:
    args = parse_args()
    _ = args.agent  # required; recorded via audit logs

    info = _load_version_info()
    if args.format == "json":
        print(json.dumps(info, indent=2, sort_keys=True))
        return 0

    print(f"Skill: {info['name']}")
    print(f"Version: {info['version']}")
    if info.get("commit"):
        print(f"Commit: {info['commit']}")
    print(f"Path: {info['path']}")
    print(f"Versioning: {info['versioning']}")
    print(f"Changelog: {info['changelog']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))

