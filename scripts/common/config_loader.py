#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_PATH = "_kano/backlog/_config/config.json"


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


def resolve_config_path(
    repo_root: Path,
    config_path: Optional[str] = None,
) -> Path:
    raw = config_path or os.getenv("KANO_BACKLOG_CONFIG_PATH") or DEFAULT_CONFIG_PATH
    path = Path(raw)
    if not path.is_absolute():
        path = (repo_root / path).resolve()
    allowed_roots = allowed_roots_for_repo(repo_root)
    if resolve_allowed_root(path, allowed_roots) is None:
        allowed = " or ".join(str(root) for root in allowed_roots)
        raise SystemExit(f"Config path must be under {allowed}: {path}")
    return path


def load_config(
    repo_root: Optional[Path] = None,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    root = repo_root or Path.cwd().resolve()
    path = resolve_config_path(root, config_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid config JSON: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a JSON object: {path}")
    return data
