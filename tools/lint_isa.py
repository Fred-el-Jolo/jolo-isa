#!/usr/bin/env python3
"""Mechanical ISA check — thin wrapper over runtime/isa/lint.py (standard library only).

Usage: tools/lint_isa.py [--moment articulation|close|auto] FILE...
Exit 0 when no file has an ERROR. Same engine as `isa lint` and the hooks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa.lint import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
