#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

# Add common directory to sys.path
COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from config_loader import get_config_value, load_config_with_defaults, validate_config
from context import get_context

# Add product_args directory if needed
from product_args import add_product_arguments

TYPE_MAP = {
    "epic": ("Epic", "EPIC", "epic"),
    "feature": ("Feature", "FTR", "feature"),
    "userstory": ("UserStory", "USR", "story"),
    "task": ("Task", "TSK", "task"),
    "bug": ("Bug", "BUG", "bug"),
}

def read_frontmatter_id(path: Path) -> Optional[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("id:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None

def find_max_number(root: Path, prefix: str) -> int:
    # Pattern to match ID-TYPE-NUMBER (e.g. KCCS-USR-0001)
    # We look for the numeric part at the end of the ID segment
    pattern = re.compile(rf"{re.escape(prefix)}-[A-Z]+-(\d{{4}})")
    max_num = 0
    if not root.exists():
        return 0
    for path in root.rglob("*.md"):
        if path.name == "README.md" or path.name.endswith(".index.md"):
            continue
        item_id = read_frontmatter_id(path)
        match = pattern.search(item_id or path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number > max_num:
            max_num = number
    return max_num

def main() -> int:
    parser = argparse.ArgumentParser(description="Find the highest number for each work item type.")
    add_product_arguments(parser)
    parser.add_argument("--prefix", help="ID prefix override.")
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    # Use get_context to resolve product
    try:
        ctx = get_context(product_arg=args.product, repo_root=repo_root)
    except Exception as e:
        print(f"Error resolving context: {e}")
        return 1
        
    product_root = ctx["product_root"]
    product_name = ctx["product_name"]

    # Load config to get prefix if not provided
    config_path = product_root / "_config" / "config.json"
    config = load_config_with_defaults(repo_root=repo_root, config_path=str(config_path) if config_path.exists() else None)
    
    prefix = args.prefix
    if not prefix:
        config_prefix = get_config_value(config, "project.prefix")
        if isinstance(config_prefix, str) and config_prefix.strip():
            prefix = config_prefix.strip()
        else:
            # Derive prefix from product name if not in config
            parts = re.split(r"[^A-Za-z0-9]+", product_name)
            prefix = "".join(p[0].upper() for p in parts if p)

    items_root = product_root / "items"
    if not items_root.exists():
        print(f"Items directory not found: {items_root}")
        return 1
    
    print(f"Product: {product_name}")
    print(f"Prefix:  {prefix}")
    print(f"Root:    {items_root}")
    print(f"{'Folder':<15} | {'Max ID'}")
    print("-" * 40)
    
    # Dynamically find folders under items/
    folders = [d for d in items_root.iterdir() if d.is_dir() and not d.name.startswith("_") and d.name != ".sandbox"]
    
    for folder_path in sorted(folders, key=lambda x: x.name):
        max_num = find_max_number(folder_path, prefix)
        if max_num > 0:
            # To get the type code, we need to peek at one file
            type_code = "???"
            for path in folder_path.rglob("*.md"):
                if path.name == "README.md" or path.name.endswith(".index.md"): continue
                item_id = read_frontmatter_id(path)
                match = re.search(rf"{re.escape(prefix)}-([A-Z]+)-\d{{4}}", item_id or path.name)
                if match:
                    type_code = match.group(1)
                    break
            print(f"{folder_path.name:<15} | {prefix}-{type_code}-{max_num:04d}")
        else:
            print(f"{folder_path.name:<15} | None")

    return 0

if __name__ == "__main__":
    sys.exit(main())
