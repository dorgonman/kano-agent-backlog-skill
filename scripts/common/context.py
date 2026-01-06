"""
Product-aware context and path resolution for multi-product monorepo architecture.

This module provides centralized functions to resolve paths in the _kano/backlog
platform structure, taking into account:
- Current product context (via CLI arg, environment variable, or defaults)
- Repo root and platform root discovery
- Product-specific directories (items, decisions, views, config, sandbox)

All path resolution in the skill should go through these functions to ensure
consistent multi-product support.

References:
- SKILL.md: Owner & Agent Assignment, multi-product architecture
- KABSD-TSK-0079: foundational task for context.py
- KABSD-FTR-0010: Monorepo Platform Migration feature
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


def find_repo_root(start_path: Optional[Path] = None) -> Path:
    """
    Find the workspace root by searching for .git directory upward.
    
    Args:
        start_path: Starting directory for search. Defaults to current working directory.
    
    Returns:
        Path to the repo root (directory containing .git).
    
    Raises:
        FileNotFoundError: If .git not found in any parent directory.
    """
    if start_path is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_path)
    
    current = start_path.resolve()
    
    while True:
        if (current / ".git").exists():
            return current
        
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding .git
            raise FileNotFoundError(
                f"Could not find repository root (.git) starting from {start_path}. "
                "Ensure you are running from within a git repository."
            )
        
        current = parent


def find_platform_root(repo_root: Optional[Path] = None) -> Path:
    """
    Find the platform root directory (_kano/backlog).
    
    Args:
        repo_root: Repo root path. If None, will call find_repo_root().
    
    Returns:
        Path to _kano/backlog.
    
    Raises:
        FileNotFoundError: If _kano/backlog does not exist.
    """
    if repo_root is None:
        repo_root = find_repo_root()
    else:
        repo_root = Path(repo_root)
    
    platform_root = repo_root / "_kano" / "backlog"
    
    if not platform_root.exists():
        raise FileNotFoundError(
            f"Platform root not found at {platform_root}. "
            "Has the backlog system been initialized?"
        )
    
    return platform_root


def load_shared_defaults(platform_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load shared defaults from _kano/backlog/_shared/defaults.json.
    
    Args:
        platform_root: Path to _kano/backlog. If None, will call find_platform_root().
    
    Returns:
        Dictionary with defaults. Minimum expected key: "default_product".
        Returns empty dict if file does not exist.
    """
    if platform_root is None:
        platform_root = find_platform_root()
    else:
        platform_root = Path(platform_root)
    
    defaults_file = platform_root / "_shared" / "defaults.json"
    
    if not defaults_file.exists():
        # Return empty dict; callers will use hardcoded fallback
        return {}
    
    try:
        with open(defaults_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        # Log warning but don't fail; callers will use fallback
        print(f"Warning: Could not parse {defaults_file}: {e}")
        return {}


def resolve_product_name(
    product_arg: Optional[str] = None,
    env_var: str = "BACKLOG_PRODUCT",
    defaults_file: Optional[Path] = None,
    platform_root: Optional[Path] = None,
) -> str:
    """
    Resolve the active product name via priority chain:
    1. product_arg (if provided and non-empty)
    2. Environment variable (if set)
    3. defaults.json -> "default_product" (if exists)
    4. Hardcoded fallback: "kano-agent-backlog-skill"
    
    Args:
        product_arg: Product name from CLI argument.
        env_var: Environment variable name to check (default: "BACKLOG_PRODUCT").
        defaults_file: Path to defaults.json. If None, will auto-discover.
        platform_root: Path to _kano/backlog. If None, will auto-discover.
    
    Returns:
        Resolved product name (non-empty string).
    """
    # Priority 1: CLI argument
    if product_arg and product_arg.strip():
        return product_arg.strip()
    
    # Priority 2: Environment variable
    env_product = os.environ.get(env_var, "").strip()
    if env_product:
        return env_product
    
    # Priority 3: defaults.json
    if defaults_file is None:
        if platform_root is None:
            platform_root = find_platform_root()
        defaults_file = Path(platform_root) / "_shared" / "defaults.json"
    
    if defaults_file.exists():
        try:
            with open(defaults_file, 'r') as f:
                defaults = json.load(f)
                default_product = defaults.get("default_product", "").strip()
                if default_product:
                    return default_product
        except (json.JSONDecodeError, IOError):
            pass  # Fall through to hardcoded fallback
    
    # Priority 4: Hardcoded fallback
    return "kano-agent-backlog-skill"


def get_product_root(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the product root directory for a given product.
    
    Args:
        product_name: Name of the product (e.g., "kano-agent-backlog-skill").
        platform_root: Path to _kano/backlog. If None, will call find_platform_root().
    
    Returns:
        Path to _kano/backlog/products/<product_name>.
    
    Raises:
        FileNotFoundError: If product directory does not exist.
    """
    if platform_root is None:
        platform_root = find_platform_root()
    else:
        platform_root = Path(platform_root)
    
    product_root = platform_root / "products" / product_name
    
    if not product_root.exists():
        raise FileNotFoundError(
            f"Product root not found at {product_root}. "
            f"Has product '{product_name}' been initialized?"
        )
    
    return product_root


def get_product_root_or_none(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Optional[Path]:
    """
    Get the product root directory, returning None if it doesn't exist (no error).
    
    Useful for checking if a product exists before operations.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog. If None, will call find_platform_root().
    
    Returns:
        Path to product root, or None if it doesn't exist.
    """
    try:
        return get_product_root(product_name, platform_root)
    except FileNotFoundError:
        return None


def get_sandbox_root(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the sandbox root directory for a given product.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog. If None, will call find_platform_root().
    
    Returns:
        Path to _kano/backlog/sandboxes/<product_name>.
    
    Raises:
        FileNotFoundError: If sandbox directory does not exist.
    """
    if platform_root is None:
        platform_root = find_platform_root()
    else:
        platform_root = Path(platform_root)
    
    sandbox_root = platform_root / "sandboxes" / product_name
    
    if not sandbox_root.exists():
        raise FileNotFoundError(
            f"Sandbox root not found at {sandbox_root}. "
            f"Has sandbox for product '{product_name}' been initialized?"
        )
    
    return sandbox_root


def get_sandbox_root_or_none(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Optional[Path]:
    """
    Get the sandbox root directory, returning None if it doesn't exist (no error).
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog. If None, will call find_platform_root().
    
    Returns:
        Path to sandbox root, or None if it doesn't exist.
    """
    try:
        return get_sandbox_root(product_name, platform_root)
    except FileNotFoundError:
        return None


def get_items_dir(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the items directory for a product.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog.
    
    Returns:
        Path to <product_root>/items.
    """
    product_root = get_product_root(product_name, platform_root)
    return product_root / "items"


def get_decisions_dir(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the decisions directory for a product.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog.
    
    Returns:
        Path to <product_root>/decisions.
    """
    product_root = get_product_root(product_name, platform_root)
    return product_root / "decisions"


def get_views_dir(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the views directory for a product.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog.
    
    Returns:
        Path to <product_root>/views.
    """
    product_root = get_product_root(product_name, platform_root)
    return product_root / "views"


def get_config_dir(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the config directory for a product.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog.
    
    Returns:
        Path to <product_root>/_config.
    """
    product_root = get_product_root(product_name, platform_root)
    return product_root / "_config"


def get_config_file(
    product_name: str,
    platform_root: Optional[Path] = None,
) -> Path:
    """
    Get the config.json file path for a product.
    
    Args:
        product_name: Name of the product.
        platform_root: Path to _kano/backlog.
    
    Returns:
        Path to <product_root>/_config/config.json.
    """
    config_dir = get_config_dir(product_name, platform_root)
    return config_dir / "config.json"


# Convenience functions for single-call resolution (common patterns)

def get_context(
    product_arg: Optional[str] = None,
    env_var: str = "BACKLOG_PRODUCT",
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Resolve full context in a single call: repo_root, platform_root, product_name, product_root.
    
    Args:
        product_arg: Product name from CLI argument.
        env_var: Environment variable name for product.
        repo_root: Repo root path. If None, will auto-discover.
    
    Returns:
        Dictionary with keys: repo_root, platform_root, product_name, product_root, sandbox_root.
    
    Raises:
        FileNotFoundError: If any path discovery fails.
    """
    if repo_root is None:
        repo_root = find_repo_root()
    else:
        repo_root = Path(repo_root)
    
    platform_root = find_platform_root(repo_root)
    product_name = resolve_product_name(product_arg, env_var, platform_root=platform_root)
    product_root = get_product_root(product_name, platform_root)
    sandbox_root = get_sandbox_root_or_none(product_name, platform_root)
    
    return {
        "repo_root": repo_root,
        "platform_root": platform_root,
        "product_name": product_name,
        "product_root": product_root,
        "sandbox_root": sandbox_root,
    }
