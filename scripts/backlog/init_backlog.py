#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import json
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
from config_loader import default_config, allowed_roots_for_repo, resolve_allowed_root  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize backlog scaffold under a permitted root."
    )
    parser.add_argument(
        "--backlog-root",
        default="_kano/backlog",
        help="Backlog root path (default: _kano/backlog).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite baseline files when they already exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files.",
    )
    return parser.parse_args()


def ensure_under_allowed(path: Path, allowed_roots: List[Path], label: str) -> None:
    if resolve_allowed_root(path, allowed_roots) is None:
        allowed = " or ".join(str(root) for root in allowed_roots)
        raise SystemExit(f"{label} must be under {allowed}: {path}")


def write_file(path: Path, content: str, force: bool, dry_run: bool) -> None:
    if path.exists() and not force:
        print(f"Skip existing: {path}")
        return
    if dry_run:
        print(f"[DRY] write {path}")
        return
    path.write_text(content, encoding="ascii")
    print(f"Wrote: {path}")


def make_dir(path: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY] mkdir {path}")
        return
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    allowed_roots = allowed_roots_for_repo(repo_root)
    backlog_root = Path(args.backlog_root)
    if not backlog_root.is_absolute():
        backlog_root = (repo_root / backlog_root).resolve()

    ensure_under_allowed(backlog_root, allowed_roots, "backlog-root")

    dirs = [
        backlog_root / "_config",
        backlog_root / "_index",
        backlog_root / "_meta",
        backlog_root / "decisions",
        backlog_root / "items" / "epics",
        backlog_root / "items" / "features",
        backlog_root / "items" / "userstories",
        backlog_root / "items" / "tasks",
        backlog_root / "items" / "bugs",
        backlog_root / "views",
        backlog_root / "tools",
    ]
    for path in dirs:
        make_dir(path, args.dry_run)

    readme_path = backlog_root / "README.md"
    readme_content = "\n".join(
        [
            "# _kano/backlog/",
            "",
            "Local-first project backlog (file-based).",
            "",
            "## Structure",
            "",
            "- `_meta/`: schema and conventions",
            "- `items/epics/`",
            "- `items/features/`",
            "- `items/userstories/`",
            "- `items/tasks/`",
            "- `items/bugs/`",
            "- `decisions/`: ADRs",
            "- `views/`: dashboards",
            "",
        ]
    )
    write_file(readme_path, readme_content, args.force, args.dry_run)

    index_path = backlog_root / "_meta" / "indexes.md"
    index_content = "\n".join(
        [
            "# Index Registry",
            "",
            "| type | item_id | index_file | updated | notes |",
            "| ---- | ------- | ---------- | ------- | ----- |",
            "",
        ]
    )
    write_file(index_path, index_content, args.force, args.dry_run)

    config_path = backlog_root / "_config" / "config.json"
    baseline = {"_comment": "Baseline config for kano-agent-backlog-skill."}
    baseline.update(default_config())
    config_content = json.dumps(baseline, indent=2, ensure_ascii=True) + "\n"
    write_file(config_path, config_content, args.force, args.dry_run)

    dashboard_index_path = backlog_root / "views" / "Dashboard.md"
    dashboard_index_content = "\n".join(
        [
            "# Dashboard",
            "",
            "This folder can host multiple view styles over the same file-first backlog items.",
            "",
            "## Plain Markdown (no plugins)",
            "",
            "- `Dashboard_PlainMarkdown.md` (embeds the generated lists)",
            "- Generated outputs: `Dashboard_PlainMarkdown_{Active,New,Done}.md`",
            "",
            "Refresh generated dashboards:",
            "- `python skills/kano-agent-backlog-skill/scripts/backlog/refresh_dashboards.py --backlog-root _kano/backlog --agent <agent-name>`",
            "",
            "## Optional: SQLite index",
            "",
            "If `index.enabled=true` in `_kano/backlog/_config/config.json`, scripts can prefer SQLite for faster reads,",
            "while Markdown files remain the source of truth.",
            "",
        ]
    )
    write_file(dashboard_index_path, dashboard_index_content, args.force, args.dry_run)

    plain_dashboard_path = backlog_root / "views" / "Dashboard_PlainMarkdown.md"
    plain_dashboard_content = "\n".join(
        [
            "# Dashboard (Plain Markdown)",
            "",
            "Embeds the generated Markdown lists (no Obsidian plugins required).",
            "",
            "![[Dashboard_PlainMarkdown_Active.md]]",
            "",
            "![[Dashboard_PlainMarkdown_New.md]]",
            "",
            "![[Dashboard_PlainMarkdown_Done.md]]",
            "",
        ]
    )
    write_file(plain_dashboard_path, plain_dashboard_content, args.force, args.dry_run)

    tools_readme_path = backlog_root / "tools" / "README.md"
    tools_readme_content = "\n".join(
        [
            "# Backlog Tools (project-specific)",
            "",
            "Keep project-only scripts here (e.g., iteration views, last-N-days focus views).",
            "Generic workflows should live in the skill under `skills/kano-agent-backlog-skill/scripts/`.",
            "",
        ]
    )
    write_file(tools_readme_path, tools_readme_content, args.force, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
