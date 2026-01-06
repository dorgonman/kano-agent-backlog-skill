#!/usr/bin/env python3
from __future__ import annotations

import sys

from _run import run_sibling_script

sys.dont_write_bytecode = True


def main() -> int:
    return run_sibling_script("view_refresh_dashboards.py", sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
