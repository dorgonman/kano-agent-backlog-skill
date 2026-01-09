from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional

import typer

from ..util import ensure_core_on_path, resolve_product_root, find_item_path_by_id

app = typer.Typer()


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import re
    import unicodedata
    
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    return slug or "untitled"


@app.command()
def read(
    item_id: str = typer.Argument(..., help="Display ID, e.g., KABSD-TSK-0001"),
    product: str | None = typer.Option(None, help="Product name under _kano/backlog/products"),
    output_format: str = typer.Option("plain", "--format", help="plain|json"),
):
    """Read a backlog item from canonical store."""
    ensure_core_on_path()
    from kano_backlog_core.canonical import CanonicalStore

    product_root = resolve_product_root(product)
    store = CanonicalStore(product_root)
    item_path = find_item_path_by_id(store.items_root, item_id)
    item = store.read(item_path)

    if output_format == "json":
        data = item.model_dump()
        # Path is not JSON serializable
        data["file_path"] = str(data.get("file_path"))
        typer.echo(json.dumps(data, ensure_ascii=False))
    else:
        typer.echo(f"ID: {item.id}\nTitle: {item.title}\nState: {item.state.value}\nOwner: {item.owner}")


@app.command()
def create(
    item_type: str = typer.Option(..., "--type", help="epic|feature|userstory|task|bug"),
    title: str = typer.Option(..., "--title", help="Work item title"),
    parent: str | None = typer.Option(None, "--parent", help="Parent item ID (optional for Epic)"),
    priority: str = typer.Option("P2", "--priority", help="Priority (default: P2)"),
    area: str = typer.Option("general", "--area", help="Area tag"),
    iteration: str | None = typer.Option(None, "--iteration", help="Iteration name"),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags"),
    owner: str | None = typer.Option(None, "--owner", help="Owner name"),
    agent: str = typer.Option(..., "--agent", help="Agent name (for audit trail)"),
    product: str | None = typer.Option(None, "--product", help="Product name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print item details without creating"),
):
    """Create a new backlog work item."""
    ensure_core_on_path()
    from kano_backlog_core.canonical import CanonicalStore, ItemType
    from lib.utils import generate_uid
    
    # Type mapping
    TYPE_MAP = {
        "epic": ("Epic", "EPIC", "epics"),
        "feature": ("Feature", "FTR", "features"),
        "userstory": ("UserStory", "USR", "userstories"),
        "task": ("Task", "TSK", "tasks"),
        "bug": ("Bug", "BUG", "bugs"),
    }
    
    type_key = item_type.lower()
    if type_key not in TYPE_MAP:
        typer.echo(f"❌ Unknown type: {item_type}. Use epic|feature|userstory|task|bug", err=True)
        raise typer.Exit(1)
    
    type_label, type_code, type_folder = TYPE_MAP[type_key]
    
    product_root = resolve_product_root(product)
    store = CanonicalStore(product_root)
    items_root = store.items_root
    
    # Find next number in sequence
    pattern = f"[A-Z]{{2,}}-{type_code}-"
    import re
    max_num = 0
    for item_file in (items_root / type_folder).rglob("*.md"):
        if item_file.name.endswith(".index.md"):
            continue
        match = re.search(rf"(\w+)-{type_code}-(\d{{4}})", item_file.stem)
        if match:
            max_num = max(max_num, int(match.group(2)))
    
    next_number = max_num + 1
    bucket = (next_number // 100) * 100
    bucket_str = f"{bucket:04d}"
    
    # Generate ID (assuming prefix is first 2-3 letters of first word in product name)
    prefix = product_root.name.split("-")[0].upper()[:2]
    item_id = f"{prefix}-{type_code}-{next_number:04d}"
    
    slug = slugify(title)
    file_name = f"{item_id}_{slug}.md"
    
    item_dir = items_root / type_folder / bucket_str
    item_path = item_dir / file_name
    
    if item_path.exists():
        typer.echo(f"❌ Item already exists: {item_path}", err=True)
        raise typer.Exit(1)
    
    if dry_run:
        typer.echo(f"✓ Would create: {item_id}")
        typer.echo(f"  Path: {item_path}")
        typer.echo(f"  Type: {type_label}")
        return
    
    # Create the item
    uid = generate_uid()
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tag_yaml = "[]" if not tag_list else "[" + ", ".join(f'"{t}"' for t in tag_list) + "]"
    
    parent_val = parent if parent else "null"
    owner_val = owner if owner else "null"
    iteration_val = iteration if iteration else "null"
    
    frontmatter = f"""---
id: {item_id}
uid: {uid}
type: {type_label}
title: "{title}"
state: Proposed
priority: {priority}
parent: {parent_val}
area: {area}
iteration: {iteration_val}
tags: {tag_yaml}
created: {date}
updated: {date}
owner: {owner_val}
external:
  azure_id: null
  jira_key: null
links:
  relates: []
  blocks: []
  blocked_by: []
decisions: []
---

# Context

# Goal

# Non-Goals

# Approach

# Alternatives

# Acceptance Criteria

# Risks / Dependencies

# Worklog

{timestamp} [agent={agent}] Created from CLI.
"""
    
    # Create directory if needed
    item_dir.mkdir(parents=True, exist_ok=True)
    
    # Write file
    item_path.write_text(frontmatter, encoding="utf-8")
    
    typer.echo(f"✓ Created: {item_id}")
    typer.echo(f"  Path: {item_path}")


@app.command()
def validate(
    item_id: str = typer.Argument(..., help="Display ID, e.g., KABSD-TSK-0001"),
    product: str | None = typer.Option(None, "--product", help="Product name"),
    output_format: str = typer.Option("plain", "--format", help="plain|json"),
):
    """Validate a work item against the Ready gate."""
    ensure_core_on_path()
    from kano_backlog_core.canonical import CanonicalStore
    
    product_root = resolve_product_root(product)
    store = CanonicalStore(product_root)
    item_path = find_item_path_by_id(store.items_root, item_id)
    item = store.read(item_path)
    
    # Ready gate fields
    ready_fields = ["context", "goal", "approach", "acceptance_criteria", "risks"]
    gaps = []
    
    for field in ready_fields:
        value = getattr(item, field, None)
        if not value or not value.strip():
            gaps.append(field)
    
    is_ready = len(gaps) == 0
    
    if output_format == "json":
        result = {
            "id": item.id,
            "is_ready": is_ready,
            "gaps": gaps,
        }
        typer.echo(json.dumps(result, ensure_ascii=False))
    else:
        if is_ready:
            typer.echo(f"✓ {item.id} is READY")
        else:
            typer.echo(f"❌ {item.id} is NOT READY")
            typer.echo("Missing fields:")
            for field in gaps:
                typer.echo(f"  - {field}")
