#!/usr/bin/env python3
"""ISC-1: every import under the given dir is stdlib or the package itself. Usage: check_stdlib.py runtime/"""
import ast
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "runtime"
bad = []
for dp, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(dp, f)
        if not (f.endswith(".py") or (os.path.basename(dp) == "bin")):
            continue
        try:
            tree = ast.parse(open(p).read())
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                   [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else []
            for m in mods:
                top = m.split(".")[0]
                if top != "isa" and top not in sys.stdlib_module_names:
                    bad.append(f"{p}: {m}")
print("\n".join(bad) or "stdlib only")
sys.exit(1 if bad else 0)
