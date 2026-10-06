#!/usr/bin/env python3
"""Lint the examples with the runtime's own rules (standard library only).

Usage: tools/lint_isa.py [--close] FILE...
A `*.spec.md` (or `docs/…-01-spec.md`) file gets the spec lint, every other file the TASK ISA lint.
Exit 0 when no file has an error.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa import lint, spec  # noqa: E402


def main(argv):
    moment = "close" if argv[:1] == ["--close"] else "draft"
    rc = 0
    for path in argv[1:] if moment == "close" else argv:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        errs = spec.lint(text) if path.endswith(("-01-spec.md", ".spec.md")) else lint.errors(text, path, moment)
        print(f"{path}: {'ok' if not errs else f'{len(errs)} error(s)'}")
        for e in errs:
            print(f"  ERROR: {e}")
        rc = max(rc, 1 if errs else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
