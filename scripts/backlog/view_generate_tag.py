#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.dont_write_bytecode = True

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from config_loader import get_config_value, load_config_with_defaults, validate_config  # noqa: E402
from product_args import add_product_arguments  # noqa: E402


def allowed_roots_for_repo(repo_root: Path) -> List[Path]:
    return [
        (repo_root / "_kano" / "backlog").resolve(),
        (repo_root / "_kano" / "backlog_sandbox").resolve(),
    ]


def resolve_allowed_root(path: Path, allowed_roots: List[Path]) -> Optional[Path]:
    resolved = path.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return root
        except ValueError:
            continue
    return None


def ensure_under_allowed(path: Path, allowed_roots: List[Path], label: str) -> Path:
    root = resolve_allowed_root(path, allowed_roots)
    if root is None:
        allowed = " or ".join(str(root) for root in allowed_roots)
        raise SystemExit(f"{label} must be under {allowed}: {path}")
    return root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown view for backlog items by tag.")
    parser.add_argument(
        "--source",
        choices=["auto", "files", "sqlite"],
        default="auto",
        help="Data source (default: auto; prefer sqlite when index.enabled=true and DB exists).",
    )
    parser.add_argument(
        "--backlog-root",
        default="_kano/backlog",
        help="Backlog root path (default: _kano/backlog).",
    )
    parser.add_argument(
        "--items-root",
        help="Backlog items root override (default: <backlog-root>/items).",
    )
    parser.add_argument(
        "--config",
        help="Optional config path override (default: KANO_BACKLOG_CONFIG_PATH or <backlog-root>/_config/config.json).",
    )
    parser.add_argument(
        "--db-path",
        help="SQLite DB path override (default: config index.path or <backlog-root>/_index/backlog.sqlite3).",
    )
    parser.add_argument(
        "--tags",
        required=True,
        help="Comma-separated tags to include (each tag becomes a section).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output markdown file path.",
    )
    parser.add_argument(
        "--title",
        default="Tag View",
        help="Document title (default: Tag View).",
    )
    parser.add_argument(
        "--agent",
        required=True,
        help="Agent identity running the script (required, used for auditability).",
    )
    add_product_arguments(parser)
    return parser.parse_args()


def resolve_config_for_backlog_root(backlog_root: Path, cli_config: Optional[str]) -> Optional[str]:
    if cli_config is not None:
        return cli_config
    if os.getenv("KANO_BACKLOG_CONFIG_PATH"):
        return None
    candidate = backlog_root / "_config" / "config.json"
    if candidate.exists():
        return str(candidate)
    return None


def resolve_db_path(repo_root: Path, backlog_root: Path, config: Dict[str, object], cli_db_path: Optional[str]) -> Path:
    db_path_raw = cli_db_path or get_config_value(config, "index.path")
    if not db_path_raw:
        db_path_raw = str((backlog_root / "_index" / "backlog.sqlite3").resolve())
    db_path = Path(str(db_path_raw))
    if not db_path.is_absolute():
        db_path = (repo_root / db_path).resolve()
    return db_path


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        return value[1:-1]
    return value


def parse_frontmatter(lines: Sequence[str]) -> Dict[str, object]:
    if not lines or str(lines[0]).strip() != "---":
        return {}
    data: Dict[str, object] = {}
    i = 1
    while i < len(lines):
        line = str(lines[i])
        if line.strip() == "---":
            break
        if ":" not in line:
            i += 1
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        raw_value = strip_quotes(raw)
        if key == "tags":
            tags: List[str] = []
            # `tags: ["a","b"]` or `tags: []`
            if raw_value.strip().startswith("["):
                inside = raw_value.strip().lstrip("[").rstrip("]")
                for part in inside.split(","):
                    part = part.strip()
                    if not part:
                        continue
                    tags.append(strip_quotes(part).strip())
                data[key] = [t for t in tags if t]
                i += 1
                continue
            # `tags:` + `- a` lines
            i += 1
            while i < len(lines):
                nxt = str(lines[i])
                if nxt.strip() == "---":
                    i -= 1
                    break
                if not nxt.strip().startswith("-"):
                    break
                tags.append(nxt.strip().lstrip("-").strip())
                i += 1
            data[key] = [t for t in tags if t]
            continue
        data[key] = raw_value.strip()
        i += 1
    return data


def open_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA query_only = ON")
    return conn


ItemRow = Tuple[str, str, str, str, str, Path]  # id, type, state, priority, title, path


def collect_from_sqlite(repo_root: Path, db_path: Path, tags: List[str]) -> Dict[str, List[ItemRow]]:
    out: Dict[str, List[ItemRow]] = {t: [] for t in tags}
    with open_readonly(db_path) as conn:
        for tag in tags:
            rows = conn.execute(
                "SELECT i.id, i.type, i.state, i.priority, i.title, i.source_path "
                "FROM items i JOIN item_tags t ON t.item_id = i.id "
                "WHERE t.tag = ? ORDER BY i.priority ASC, i.updated DESC, i.id ASC",
                (tag,),
            ).fetchall()
            for item_id, item_type, state, priority, title, source_path in rows:
                rel = Path(str(source_path or "").replace("\\", "/"))
                out[tag].append(
                    (
                        str(item_id or "").strip(),
                        str(item_type or "").strip(),
                        str(state or "").strip(),
                        str(priority or "").strip(),
                        str(title or "").strip(),
                        (repo_root / rel).resolve(),
                    )
                )
    return out


def collect_from_files(items_root: Path, tags: List[str]) -> Dict[str, List[ItemRow]]:
    wanted = set(tags)
    out: Dict[str, List[ItemRow]] = {t: [] for t in tags}
    for path in items_root.rglob("*.md"):
        if path.name == "README.md" or path.name.endswith(".index.md"):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        data = parse_frontmatter(lines)
        item_tags = data.get("tags")
        if not isinstance(item_tags, list) or not item_tags:
            continue
        match = [t for t in item_tags if isinstance(t, str) and t in wanted]
        if not match:
            continue
        item_id = str(data.get("id") or "").strip()
        item_type = str(data.get("type") or "").strip()
        state = str(data.get("state") or "").strip()
        priority = str(data.get("priority") or "").strip()
        title = str(data.get("title") or "").strip()
        if not item_id or not item_type:
            continue
        row = (item_id, item_type, state, priority, title, path)
        for tag in match:
            out[tag].append(row)
    return out


def format_items(
    grouped: Dict[str, List[ItemRow]],
    output_path: Path,
    title: str,
    source_label: str,
    tags: List[str],
) -> str:
    out_dir = output_path.parent
    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Source: {source_label}")
    lines.append(f"Tags: {', '.join(tags)}")
    lines.append("")

    for tag in tags:
        lines.append(f"## {tag}")
        lines.append("")
        rows = grouped.get(tag, [])
        if not rows:
            lines.append("_No items._")
            lines.append("")
            continue
        # Priority ordering for common P0..P3 then fallback; keep stable by id
        def prio_key(value: str) -> int:
            return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(value.strip().upper(), 99)

        for item_id, item_type, state, priority, title_text, path in sorted(
            rows, key=lambda r: (prio_key(r[3]), r[0])
        ):
            text = f"{item_id} {title_text}".strip()
            rel = os.path.relpath(path, out_dir).replace("\\", "/")
            meta = " ".join(part for part in [f"type={item_type}", f"state={state}", f"priority={priority}"] if part and part != "priority=")
            suffix = f" ({meta})" if meta else ""
            lines.append(f"- [{text}]({rel}){suffix}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    _ = args.agent  # required; recorded via audit logs

    repo_root = Path.cwd().resolve()
    allowed_roots = allowed_roots_for_repo(repo_root)

    backlog_root = Path(args.backlog_root)
    if not backlog_root.is_absolute():
        backlog_root = (repo_root / backlog_root).resolve()
    ensure_under_allowed(backlog_root, allowed_roots, "backlog-root")

    items_root = Path(args.items_root) if args.items_root else (backlog_root / "items")
    if not items_root.is_absolute():
        items_root = (repo_root / items_root).resolve()
    ensure_under_allowed(items_root, allowed_roots, "items-root")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (repo_root / output_path).resolve()
    ensure_under_allowed(output_path, allowed_roots, "output")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not tags:
        raise SystemExit("--tags is empty.")

    config_path = resolve_config_for_backlog_root(backlog_root, args.config)
    config = load_config_with_defaults(repo_root=repo_root, config_path=config_path)
    errors = validate_config(config)
    if errors:
        raise SystemExit("Invalid config:\n- " + "\n- ".join(errors))

    db_path = resolve_db_path(repo_root, backlog_root, config, args.db_path)
    ensure_under_allowed(db_path, allowed_roots, "db-path")

    index_enabled = bool(get_config_value(config, "index.enabled", False))
    use_sqlite = False
    if args.source == "sqlite":
        use_sqlite = True
    elif args.source == "files":
        use_sqlite = False
    else:
        use_sqlite = index_enabled and db_path.exists()

    source_label = ""
    if use_sqlite:
        if not db_path.exists():
            if args.source == "auto":
                use_sqlite = False
            else:
                raise SystemExit(f"DB does not exist: {db_path}\nRun scripts/indexing/build_sqlite_index.py first.")
    if use_sqlite:
        source_label = f"sqlite:{db_path.as_posix()}"
        grouped = collect_from_sqlite(repo_root, db_path, tags)
    else:
        source_label = f"files:{items_root.as_posix()}"
        grouped = collect_from_files(items_root, tags)

    output_path.write_text(format_items(grouped, output_path, args.title, source_label, tags), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))

