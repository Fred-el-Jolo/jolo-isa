#!/usr/bin/env python3
"""Check what git stored for a repo's ISAs (SPEC-v2 § 13.5): every quoting form of a committed `.isa/**/*.md` is
encrypted, and the root `ISA.md` holds no ciphertext. Reads `git show <rev>:<path>`, never the working tree.

    python3 tools/check_committed_isas.py [REV]     (default HEAD) → exit 0 when clean
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from isa import crypt  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main(rev="HEAD"):
    bad, n = [], 0
    for path in git("ls-tree", "-r", "--name-only", rev).splitlines():
        if not (path.startswith(".isa/") and path.endswith(".md")) and path != "ISA.md":
            continue
        n += 1
        blob = git("show", f"{rev}:{path}")
        if path == "ISA.md":
            if "enc:v1:" in blob:
                bad.append(f"{path}: the project ISA holds ciphertext (it must stay plain)")
            continue
        plain = crypt.plain_spans(blob)
        if plain:
            bad.append(f"{path}: {len(plain)} quote(s) stored in plain text, e.g. {plain[0][:40]!r}")
    for b in bad:
        print(b)
    print(f"{n} ISA file(s) checked at {rev}: {'ok' if not bad else f'{len(bad)} problem(s)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
