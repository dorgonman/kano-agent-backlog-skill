#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.dont_write_bytecode = True

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from config_loader import get_config_value, load_config_with_defaults, validate_config  # noqa: E402
from context import find_platform_root, get_product_root, get_sandbox_root_or_none, resolve_product_name  # noqa: E402
from product_args import add_product_arguments, get_product_and_sandbox_flags  # noqa: E402


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


STATE_GROUPS = {
    "Proposed": "New",
    "Planned": "New",
    "Ready": "New",
    "New": "New",
    "InProgress": "InProgress",
    "Review": "InProgress",
    "Blocked": "InProgress",
    "Done": "Done",
    "Dropped": "Done",
}

TYPE_ORDER = ["Epic", "Feature", "UserStory", "Task", "Bug"]
TYPE_LABELS = {
    "Epic": "Epics",
    "Feature": "Features",
    "UserStory": "UserStories",
    "Task": "Tasks",
    "Bug": "Bugs",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown view for backlog items.")
    parser.add_argument(
        "--source",
        choices=["auto", "files", "sqlite"],
        default="auto",
        help="Data source (default: auto; prefer sqlite when index.enabled=true and DB exists).",
    )
    parser.add_argument(
        "--items-root",
        default="_kano/backlog/items",
        help="Backlog items root (default: _kano/backlog/items).",
    )
    parser.add_argument(
        "--backlog-root",
        help="Backlog root path override (default: parent of --items-root).",
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
        "--output",
        required=True,
        help="Output markdown file path.",
    )
    parser.add_argument(
        "--groups",
        default="New,InProgress",
        help="Comma-separated groups to include (default: New,InProgress).",
    )
    parser.add_argument(
        "--title",
        default="InProgress Work",
        help="Document title (default: InProgress Work).",
    )
    parser.add_argument(
        "--source-label",
        help="Optional label shown in output (default: --items-root).",
    )
    parser.add_argument(
        "--products",
        action="append",
        help="Comma-separated product names to aggregate (repeatable).",
    )
    parser.add_argument(
        "--all-products",
        action="store_true",
        help="Aggregate across all products under the platform root.",
    )
    add_product_arguments(parser)
    return parser.parse_args()


def resolve_config_for_backlog_root(repo_root: Path, backlog_root: Path, cli_config: Optional[str]) -> Optional[str]:
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


def parse_frontmatter(path: Path) -> Dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data: Dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        value = strip_quotes(raw)
        data[key] = value
    return data


def is_legacy_plural_product_items_path(path: Path) -> bool:
    parts = list(path.as_posix().split("/"))
    try:
        items_idx = parts.index("items")
    except ValueError:
        return False
    if "products" not in parts:
        return False
    if items_idx + 1 >= len(parts):
        return False
    next_dir = parts[items_idx + 1]
    legacy_plural = {"epics", "features", "tasks", "userstories", "bugs"}
    return next_dir in legacy_plural


def collect_items(
    root: Path,
    allowed_groups: List[str],
) -> Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]]:
    groups: Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]] = {}
    for path in root.rglob("*.md"):
        if is_legacy_plural_product_items_path(path):
            continue
        if path.name == "README.md" or path.name.endswith(".index.md"):
            continue
        # Use full YAML parser to get links properly if available
        try:
            from lib.utils import parse_frontmatter as parse_fm
            content = path.read_text(encoding="utf-8")
            data, _, _ = parse_fm(content)
        except Exception:
            # Fallback to simple parser
            data = parse_frontmatter(path)
            
        item_id = str(data.get("id", "")).strip()
        item_type = str(data.get("type", "")).strip()
        state = str(data.get("state", "")).strip()
        title = str(data.get("title", "")).strip()
        if not item_id or not item_type or not state:
            continue
        group = STATE_GROUPS.get(state)
        if group not in allowed_groups:
            continue
            
        links = data.get("links", {})
        link_summary = {
            "blocks": links.get("blocks", []) if isinstance(links, dict) else [],
            "blocked_by": links.get("blocked_by", []) if isinstance(links, dict) else []
        }
        groups.setdefault(group, {}).setdefault(item_type, []).append((item_id, title, path, link_summary))
    return groups


def open_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA query_only = ON")
    return conn


def collect_items_from_sqlite(
    repo_root: Path,
    db_path: Path,
    allowed_groups: List[str],
) -> Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]]:
    groups: Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]] = {}
    with open_readonly(db_path) as conn:
        rows = conn.execute("SELECT id, type, state, title, source_path FROM items").fetchall()
        # Fetch all links in one go for efficiency
        links_rows = conn.execute("SELECT item_id, relation, target FROM item_links WHERE relation IN ('blocks', 'blocked_by')").fetchall()
        item_links: Dict[str, Dict[str, List[str]]] = {}
        for mid, rel, tgt in links_rows:
            item_links.setdefault(mid, {}).setdefault(rel, []).append(tgt)
            
    for item_id, item_type, state, title, source_path in rows:
        item_id = str(item_id or "").strip()
        item_type = str(item_type or "").strip()
        state = str(state or "").strip()
        title = str(title or "").strip()
        if not item_id or not item_type or not state:
            continue
        group = STATE_GROUPS.get(state)
        if group not in allowed_groups:
            continue
        source = Path(str(source_path or "").replace("\\", "/"))
        path = (repo_root / source).resolve()
        
        link_summary = item_links.get(item_id, {"blocks": [], "blocked_by": []})
        groups.setdefault(group, {}).setdefault(item_type, []).append((item_id, title, path, link_summary))
    return groups


def pluralize_label(item_type: str) -> str:
    if item_type in TYPE_LABELS:
        return TYPE_LABELS[item_type]
    if item_type.endswith("s"):
        return item_type
    return f"{item_type}s"


def format_items(
    groups: Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]],
    output_path: Path,
    title: str,
    allowed_groups: List[str],
    source_label: str,
    command: Optional[str],
) -> List[str]:
    out_dir = output_path.parent
    lines: List[str] = []
    lines.append(f"# {title}")
    lines.append("")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"Generated: {timestamp}")
    lines.append(f"Source: {source_label}")
    if command:
        lines.append("Command:")
        lines.append("")
        lines.append("```bash")
        lines.append(command)
        lines.append("```")
    lines.append("")

    for group in allowed_groups:
        lines.append(f"## {group}")
        lines.append("")
        group_items = groups.get(group, {})
        all_types = list(group_items.keys())
        type_order = TYPE_ORDER + sorted([t for t in all_types if t not in TYPE_ORDER])
        has_any = any(group_items.get(item_type) for item_type in type_order)
        if not has_any:
            lines.append("_No items._")
            lines.append("")
            continue
        for item_type in type_order:
            items = group_items.get(item_type, [])
            if not items:
                continue
            label = pluralize_label(item_type)
            lines.append(f"### {label}")
            lines.append("")
            for item_id, item_title, path, links in sorted(items, key=lambda item: item[0]):
                display_text = f"{item_id} {item_title}".strip()
                
                # Dependency indicators
                indicators = []
                blocked_by = links.get("blocked_by", [])
                blocks = links.get("blocks", [])
                
                if blocked_by:
                    refs = ", ".join(blocked_by)
                    indicators.append(f"🔴 Blocked by: {refs}")
                if blocks:
                    refs = ", ".join(blocks)
                    indicators.append(f"⛓️ Blocks: {refs}")
                
                if indicators:
                    display_text += " [" + " | ".join(indicators) + "]"
                
                rel = os.path.relpath(path, out_dir).replace("\\", "/")
                lines.append(f"- [{display_text}]({rel})")
            lines.append("")
    return lines


def parse_products_values(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    products: List[str] = []
    for raw in values:
        if not raw:
            continue
        for part in raw.split(","):
            name = part.strip()
            if name:
                products.append(name)
    deduped: List[str] = []
    seen: set[str] = set()
    for name in products:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def list_all_products(platform_root: Path) -> List[str]:
    products_dir = platform_root / "products"
    if not products_dir.exists():
        return []
    names: List[str] = []
    for entry in sorted(products_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            names.append(entry.name)
    return names


def merge_groups(
    target: Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]],
    source: Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]],
) -> None:
    for group, types in source.items():
        for item_type, items in types.items():
            target.setdefault(group, {}).setdefault(item_type, []).extend(items)


def path_to_repo_relative(repo_root: Path, raw: str) -> str:
    try:
        p = Path(raw)
    except Exception:
        return raw
    if not p.is_absolute():
        return raw.replace("\\", "/")
    try:
        rel = p.resolve().relative_to(repo_root.resolve())
        return str(rel).replace("\\", "/")
    except Exception:
        return raw.replace("\\", "/")


def normalize_cli_token(repo_root: Path, token: str) -> str:
    if not token:
        return token
    if token.startswith("-"):
        return token
    looks_like_path = ("/" in token) or ("\\" in token) or token.startswith(".")
    if not looks_like_path:
        return token
    rendered = path_to_repo_relative(repo_root, token)
    if " " in rendered:
        return f'"{rendered}"'
    return rendered


def command_from_argv(repo_root: Path) -> str:
    argv = list(sys.argv)
    if not argv:
        return "python"
    raw_script = argv[0]
    script_token = raw_script
    try:
        script_path = Path(raw_script)
        if not script_path.is_absolute():
            script_path = (repo_root / script_path).resolve()
        script_token = path_to_repo_relative(repo_root, str(script_path))
    except Exception:
        script_token = raw_script

    normalized_args = [normalize_cli_token(repo_root, tok) for tok in argv[1:]]
    cmd = "python"
    if script_token:
        cmd += f" {normalize_cli_token(repo_root, script_token)}"
    if normalized_args:
        cmd += " " + " ".join(normalized_args)
    return cmd


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    allowed_roots = allowed_roots_for_repo(repo_root)
    allowed_groups = [group.strip() for group in args.groups.split(",") if group.strip()]

    products = parse_products_values(getattr(args, "products", None))
    if getattr(args, "all_products", False):
        if products:
            raise SystemExit("--products and --all-products cannot be used together.")
        platform_root = find_platform_root(repo_root)
        products = list_all_products(platform_root)

    product_name, use_sandbox = get_product_and_sandbox_flags(args)
    if product_name and products:
        raise SystemExit("Use either --product or --products/--all-products, not both.")
    items_root = Path(args.items_root)
    if not items_root.is_absolute():
        items_root = (repo_root / items_root).resolve()
    items_root_root = ensure_under_allowed(items_root, allowed_roots, "items-root")

    backlog_root = Path(args.backlog_root) if args.backlog_root else items_root.parent
    if not backlog_root.is_absolute():
        backlog_root = (repo_root / backlog_root).resolve()
    backlog_root_root = ensure_under_allowed(backlog_root, allowed_roots, "backlog-root")
    if backlog_root_root != items_root_root:
        raise SystemExit("items-root and backlog-root must share the same root.")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (repo_root / output_path).resolve()
    output_root = ensure_under_allowed(output_path, allowed_roots, "output")
    if output_root != items_root_root:
        raise SystemExit("items-root and output must share the same root.")

    if product_name:
        product_name = resolve_product_name(product_name, platform_root=find_platform_root(repo_root))
        products = [product_name]

    groups: Dict[str, Dict[str, List[Tuple[str, str, Path, Dict[str, List[str]]]]]] = {}
    source_label = args.source_label or args.items_root
    if not args.source_label:
        source_label = path_to_repo_relative(repo_root, str(source_label))
    cmd = command_from_argv(repo_root)

    if products:
        platform_root = find_platform_root(repo_root)
        if args.source_label:
            source_label = args.source_label
        else:
            source_label = f"products:{','.join(products)}"
        for name in products:
            product_root = (
                (get_sandbox_root_or_none(name, platform_root) or (platform_root / "sandboxes" / name))
                if use_sandbox
                else get_product_root(name, platform_root)
            )
            items_path = product_root / "items"
            ensure_under_allowed(items_path, allowed_roots, "items-root")

            config = load_config_with_defaults(repo_root=repo_root, config_path=args.config, product_name=name)
            errors = validate_config(config)
            if errors:
                raise SystemExit("Invalid config:\n- " + "\n- ".join(errors))
            db_path = resolve_db_path(repo_root, product_root, config, args.db_path)
            ensure_under_allowed(db_path, allowed_roots, "db-path")

            index_enabled = bool(get_config_value(config, "index.enabled", False))
            use_sqlite = False
            if args.source == "sqlite":
                use_sqlite = True
            elif args.source == "files":
                use_sqlite = False
            else:
                use_sqlite = index_enabled and db_path.exists()

            if use_sqlite:
                if not db_path.exists():
                    raise SystemExit(
                        f"DB does not exist: {db_path}\nRun scripts/indexing/build_sqlite_index.py first."
                    )
                if args.source_label:
                    source_label = args.source_label
                else:
                    source_label = f"sqlite:{path_to_repo_relative(repo_root, db_path.as_posix())}"
                merge_groups(groups, collect_items_from_sqlite(repo_root, db_path, allowed_groups))
            else:
                merge_groups(groups, collect_items(items_path, allowed_groups))
    else:
        config = load_config_with_defaults(repo_root=repo_root, config_path=args.config)
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

        if use_sqlite:
            if not db_path.exists():
                raise SystemExit(
                    f"DB does not exist: {db_path}\nRun scripts/indexing/build_sqlite_index.py first."
                )
            if args.source_label:
                source_label = args.source_label
            else:
                source_label = f"sqlite:{path_to_repo_relative(repo_root, db_path.as_posix())}"
            groups = collect_items_from_sqlite(repo_root, db_path, allowed_groups)
        else:
            if args.source == "auto" and index_enabled and not db_path.exists():
                if args.source_label:
                    source_label = args.source_label
                else:
                    source_label = f"files:{path_to_repo_relative(repo_root, str(args.items_root))} (sqlite missing, fallback)"
            groups = collect_items(items_root, allowed_groups)
    output_lines = format_items(groups, output_path, args.title, allowed_groups, source_label, cmd)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
