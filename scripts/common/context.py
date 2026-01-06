from pathlib import Path
import json
import os
from typing import Optional, Dict, Any

# Constants
PLATFORM_ROOT_REL = "_kano/backlog"
PRODUCTS_DIR_REL = "products"
SANDBOXES_DIR_REL = "sandboxes"
SHARED_DIR_REL = "_shared"
DEFAULTS_FILE = "defaults.json"

def get_repo_root() -> Path:
    """
    Find the repository root. 
    Assumes this script is running from within the repo.
    We can search for .git or just assume a known structure relative to this file?
    This file is in skills/kano-agent-backlog-skill/scripts/backlog/lib/context.py
    So repo root is parents[5].
    """
    # Fallback to CWD if we can't determine from __file__ (e.g. interactive)
    try:
        current = Path(__file__).resolve()
        # skills/kano-agent-backlog-skill/scripts/backlog/lib/context.py -> 6 levels up?
        # 1: lib, 2: backlog, 3: scripts, 4: kano-agent-backlog-skill, 5: skills, 6: root
        return current.parents[5]
    except NameError:
        return Path.cwd()

def get_platform_root(repo_root: Optional[Path] = None) -> Path:
    root = repo_root or get_repo_root()
    return root / PLATFORM_ROOT_REL

def get_shared_defaults(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    platform = get_platform_root(repo_root)
    defaults_path = platform / SHARED_DIR_REL / DEFAULTS_FILE
    if defaults_path.exists():
        try:
            return json.loads(defaults_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}

def resolve_product(product_name: Optional[str] = None, repo_root: Optional[Path] = None) -> str:
    """
    Determine the target product.
    Priority:
    1. Explicit product_name argument
    2. KANO_BACKLOG_PRODUCT env var
    3. default_product from defaults.json
    4. 'kano-agent-backlog-skill' (hard implicit fallback)
    """
    if product_name:
        return product_name
    
    env_prod = os.getenv("KANO_BACKLOG_PRODUCT")
    if env_prod:
        return env_prod
        
    defaults = get_shared_defaults(repo_root)
    return defaults.get("default_product", "kano-agent-backlog-skill")

def get_product_root(product_name: str, is_sandbox: bool = False, repo_root: Optional[Path] = None) -> Path:
    platform = get_platform_root(repo_root)
    category = SANDBOXES_DIR_REL if is_sandbox else PRODUCTS_DIR_REL
    return platform / category / product_name
