#!/usr/bin/env python3
"""Parity: runtime/isa/lint.py (stdlib) reports exactly what tools/lint_isa.py (PyYAML)
reported, on every example and every broken fixture. Needs PyYAML on PYTHONPATH.
Kept until the PyYAML linter is retired; tools/lint_isa.py now wraps the runtime one."""
import glob
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import lint as new  # noqa: E402

GOLDEN = os.path.join(ROOT, "tests", "fixtures", "lint_isa_pyyaml.py")
spec = importlib.util.spec_from_file_location("old", GOLDEN)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

files = sorted(glob.glob(os.path.join(ROOT, "skill/ISA/Examples/*.md"))
               + glob.glob(os.path.join(ROOT, "tests/fixtures/broken/*.md")))
bad = 0
for f in files:
    a = old.lint(f, "auto").items
    b = new.lint(f, "auto").items
    norm = lambda items: [(lvl, m.split(": ", 1)[0] if "YAML does not parse" in m else m) for lvl, m in items]
    if norm(a) != norm(b):
        bad += 1
        print("DIFF", os.path.relpath(f, ROOT))
        for x in sorted(set(norm(a)) ^ set(norm(b))):
            print("   ", "old" if x in norm(a) else "new", x)
print(f"{len(files) - bad}/{len(files)} files identical")
sys.exit(1 if bad else 0)
