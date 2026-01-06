#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

LOGGING_DIR = Path(__file__).resolve().parents[1] / "logging"
if str(LOGGING_DIR) not in sys.path:
    sys.path.insert(0, str(LOGGING_DIR))
from audit_runner import run_with_audit  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose Windows file lock/read-only conditions."
    )
    parser.add_argument("--path", required=True, help="Path to diagnose.")
    return parser.parse_args()


def print_readonly_hint(path: Path) -> None:
    if not path.exists():
        print(f"Path not found: {path}")
        return
    if not os.access(path, os.W_OK):
        print("File is not writable (read-only or ACL restrictions).")


def run_handle(path: Path) -> int:
    handle_exe = shutil.which("handle.exe") or shutil.which("handle")
    if not handle_exe:
        print(
            "handle.exe not found on PATH. "
            "You can install Sysinternals and run: handle.exe -accepteula <path>"
        )
        return 1
    cmd = [handle_exe, "-accepteula", str(path)]
    result = subprocess.run(cmd, text=True, capture_output=True)
    output = result.stdout.strip() or result.stderr.strip()
    if output:
        print(output)
    return result.returncode


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    print_readonly_hint(path)
    return run_handle(path)


if __name__ == "__main__":
    raise SystemExit(run_with_audit(main))
