#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

sys.dont_write_bytecode = True


def run_sibling_script(script_name: str, argv: List[str]) -> int:
    # <skill>/scripts/backlog/cli/_run.py -> <skill>/scripts/backlog/<script_name>
    target = Path(__file__).resolve().parents[1] / script_name
    cmd = [sys.executable, str(target), *argv]
    result = subprocess.run(cmd)
    return int(result.returncode or 0)

