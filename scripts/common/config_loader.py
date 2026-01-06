#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_PATH = "_kano/backlog/_config/config.json"
DEFAULT_CONFIG = {
    "project": {
        "name": None,
        "prefix": None,
    },
    "log": {
        "verbosity": "info",
        "debug": False,
    },
    "process": {
        "profile": "builtin/azure-boards-agile",
        "path": None,
    },
    "sandbox": {
        "root": "_kano/backlog_sandbox",
    },
    "index": {
        "enabled": False,
        "backend": "sqlite",
        "path": None,
        "mode": "rebuild",
    },
}


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


def default_config() -> Dict[str, Any]:
    return copy.deepcopy(DEFAULT_CONFIG)


def merge_defaults(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_defaults(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config_with_defaults(
    repo_root: Optional[Path] = None,
    config_path: Optional[str] = None,
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = defaults if defaults is not None else default_config()
    overrides = load_config(repo_root=repo_root, config_path=config_path)
    if not overrides:
        return base
    return merge_defaults(base, overrides)


def get_config_value(config: Dict[str, Any], path: str, default: Any = None) -> Any:
    if not config or not path:
        return default
    current: Any = config
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return default
        current = current[segment]
    return current


def validate_config(config: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(config, dict):
        return ["Config must be a JSON object."]

    project_cfg = config.get("project", {})
    if project_cfg is not None and not isinstance(project_cfg, dict):
        errors.append("project must be an object.")
    else:
        name = project_cfg.get("name") if isinstance(project_cfg, dict) else None
        if name is not None and not isinstance(name, str):
            errors.append("project.name must be a string or null.")
        prefix = project_cfg.get("prefix") if isinstance(project_cfg, dict) else None
        if prefix is not None and not isinstance(prefix, str):
            errors.append("project.prefix must be a string or null.")
        elif isinstance(prefix, str):
            trimmed = prefix.strip()
            if trimmed and not trimmed.isalnum():
                errors.append("project.prefix must be alphanumeric (A-Z0-9).")

    log_cfg = config.get("log", {})
    if log_cfg is not None and not isinstance(log_cfg, dict):
        errors.append("log must be an object.")
    else:
        verbosity = log_cfg.get("verbosity") if isinstance(log_cfg, dict) else None
        if verbosity is not None and not isinstance(verbosity, str):
            errors.append("log.verbosity must be a string.")
        elif isinstance(verbosity, str):
            allowed = {"info", "debug", "warn", "warning", "error", "off", "none", "disabled"}
            if verbosity.strip().lower() not in allowed:
                errors.append("log.verbosity must be one of: info, debug, warn, error, off.")
        debug = log_cfg.get("debug") if isinstance(log_cfg, dict) else None
        if debug is not None and not isinstance(debug, bool):
            errors.append("log.debug must be a boolean.")

    process_cfg = config.get("process", {})
    if process_cfg is not None and not isinstance(process_cfg, dict):
        errors.append("process must be an object.")
    else:
        profile = process_cfg.get("profile") if isinstance(process_cfg, dict) else None
        if profile is not None and not isinstance(profile, str):
            errors.append("process.profile must be a string or null.")
        path_value = process_cfg.get("path") if isinstance(process_cfg, dict) else None
        if path_value is not None and not isinstance(path_value, str):
            errors.append("process.path must be a string or null.")

    index_cfg = config.get("index", {})
    if index_cfg is not None and not isinstance(index_cfg, dict):
        errors.append("index must be an object.")
    else:
        enabled = index_cfg.get("enabled") if isinstance(index_cfg, dict) else None
        if enabled is not None and not isinstance(enabled, bool):
            errors.append("index.enabled must be a boolean.")

        backend = index_cfg.get("backend") if isinstance(index_cfg, dict) else None
        if backend is not None and not isinstance(backend, str):
            errors.append("index.backend must be a string or null.")
        elif isinstance(backend, str):
            allowed_backends = {"sqlite", "postgres"}
            if backend.strip().lower() not in allowed_backends:
                errors.append("index.backend must be one of: sqlite, postgres.")

        path_value = index_cfg.get("path") if isinstance(index_cfg, dict) else None
        if path_value is not None and not isinstance(path_value, str):
            errors.append("index.path must be a string or null.")

        mode = index_cfg.get("mode") if isinstance(index_cfg, dict) else None
        if mode is not None and not isinstance(mode, str):
            errors.append("index.mode must be a string or null.")
        elif isinstance(mode, str):
            allowed_modes = {"rebuild", "incremental"}
            if mode.strip().lower() not in allowed_modes:
                errors.append("index.mode must be one of: rebuild, incremental.")

    sandbox_cfg = config.get("sandbox", {})
    if sandbox_cfg is not None and not isinstance(sandbox_cfg, dict):
        errors.append("sandbox must be an object.")
    else:
        root = sandbox_cfg.get("root") if isinstance(sandbox_cfg, dict) else None
        if root is not None and not isinstance(root, str):
            errors.append("sandbox.root must be a string.")

    return errors
