#!/usr/bin/env python3
"""Mechanical ISA check — thin wrapper over runtime/isa/lint.py (standard library only).

Usage: tools/lint_isa.py [--moment articulation|close|auto] FILE...
Exit 0 when no file has an ERROR. Same engine as `isa lint` and the hooks.

The worked spec examples go to the spec lint at the ack moment (`specdoc.lint(path, "ack")`): a file named
`*.spec.md` or `*.plan.md`, or one under `docs/spec/` / `docs/plan/`. A plan names its spec as `docs/spec/<name>`
from its doc root, which the examples folder isn't, so an example plan is linted in a temporary
`docs/spec/` + `docs/plan/` copy, with its sibling `<example>.spec.md` under the name the plan gives.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa import lint, specdoc  # noqa: E402


def is_doc(path):
    p = os.path.abspath(path)
    return (p.endswith((".spec.md", ".plan.md"))
            or os.path.basename(os.path.dirname(p)) in ("spec", "plan")
            and os.path.basename(os.path.dirname(os.path.dirname(p))) == "docs")


def doc_items(path):
    """The spec lint's messages for a spec, or for an example plan read beside its sibling spec."""
    if not path.endswith(".plan.md"):
        return specdoc.lint(path, "ack")
    with open(path, encoding="utf-8") as f:
        fm = specdoc.parse(f.read())["fm"]
    name = os.path.basename(str(fm.get("spec") or "spec.md"))
    tmp = tempfile.mkdtemp(prefix="lint-isa-")
    try:
        for sub, src in (("plan", path), ("spec", path[:-len(".plan.md")] + ".spec.md")):
            os.makedirs(os.path.join(tmp, "docs", sub))
            if os.path.exists(src):
                shutil.copyfile(src, os.path.join(tmp, "docs", sub, name))
        return specdoc.lint(os.path.join(tmp, "docs", "plan", name), "ack")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    flags = argv[:2] if argv[:1] == ["--moment"] else argv[:1] if argv[:1] == ["--close"] else []
    files = argv[len(flags):]
    rc = 0
    for p in files:
        if not is_doc(p):
            rc = max(rc, lint.main(flags + [p]))
            continue
        items = doc_items(p)
        errs = [m for m in items if not m.startswith("warn:")]
        print(f"{p}: {'ok' if not errs else f'{len(errs)} error(s)'}")
        for m in items:
            print(f"  WARN: {m[len('warn:'):].strip()}" if m.startswith("warn:") else f"  ERROR: {m}")
        rc = max(rc, 1 if errs else 0)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
