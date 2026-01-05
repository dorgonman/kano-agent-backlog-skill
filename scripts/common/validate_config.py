#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402

COMMON_DIR = Path(__file__).resolve().parent
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))
from config_loader import (  # noqa: E402
    load_config,
    resolve_config_path,
    validate_config,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate kano-agent-backlog-skill config.")
    parser.add_argument(
        "--config-path",
        help="Config path override (default: _kano/backlog/_config/config.json).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd().resolve()
    config_path = resolve_config_path(repo_root, args.config_path)
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return 1

    config = load_config(repo_root=repo_root, config_path=str(config_path))
    errors = validate_config(config)
    if errors:
        print("Config validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Config OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
