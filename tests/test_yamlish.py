#!/usr/bin/env python3
"""Parity: runtime/isa/yamlish.load must equal yaml.safe_load on every YAML block
of every example (frontmatter, Test Strategy, Features) plus the edge cases below.

Needs PyYAML on PYTHONPATH (dev only). Usage: python3 tests/test_yamlish.py [extra.md ...]
"""
import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import yamlish  # noqa: E402

EDGE = [
    "a: 1\nb: -2\nc: 1.5\nd: true\ne: null\nf: ~\ng:\n",
    "k: 'it''s'\nq: \"a\\tb \\\"c\\\"\"\n",
    "l: [ISC-1, ISC-2.1, 'x, y']\nm: []\n",
    "- isc: ISC-1\n  tool: |-\n    curl -s 'a' | jq '.x'\n    second line\n  after: ok\n",
    "t: >-\n  folded\n  text\n\n  para\n",
    "k: v  # comment\n# full comment\nh: 'a # not comment'\n",
    "- a\n- b\n-\n  - nested\n",
    "outer:\n  inner: 1\n  list:\n  - x\n  - y\n",
    "v: 2026-09-25T12:11:57+02:00\n",
]


BAD = [
    "threshold: 100% Content-Type: image/webp\n",
    "threshold: \"Live on Spotify\" by 2026-05-15\n",
    "threshold: |reads| == |audit_events|\n",
    "a: 1\n  b: 2\n",
    "- a\nb: 1\n",
]


def blocks(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m:
        yield "frontmatter", m.group(1)
    for sec in ("Test Strategy", "Features"):
        s = re.search(r"^## " + sec + r"\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if s:
            b = re.search(r"```ya?ml\n(.*?)```", s.group(1), re.S)
            if b:
                yield sec, b.group(1)


def norm(x):
    # PyYAML turns ISO timestamps into datetime objects; ISA readers treat them as strings.
    import datetime
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm(v) for v in x]
    if isinstance(x, (datetime.date, datetime.datetime)):
        return "DATE"
    return x


def norm_ours(x):
    if isinstance(x, dict):
        return {k: norm_ours(v) for k, v in x.items()}
    if isinstance(x, list):
        return [norm_ours(v) for v in x]
    if isinstance(x, str) and re.match(r"^\d{4}-\d{2}-\d{2}([T ][\d:.]+([+-]\d{2}:\d{2}|Z)?)?$", x):
        return "DATE"
    return x


def main(extra):
    files = sorted(glob.glob(os.path.join(ROOT, "skill/ISA/Examples/*.md"))) + extra
    fails = n = 0
    cases = [(f"edge#{i}", "edge", t) for i, t in enumerate(EDGE)]
    for f in files:
        cases += [(os.path.basename(f), name, b) for name, b in blocks(open(f).read())]
    for where, name, text in cases:
        n += 1
        want = norm(yaml.safe_load(text))
        try:
            got = norm_ours(yamlish.load(text))
        except yamlish.YamlError as e:
            got = f"YamlError: {e}"
        if got != want:
            fails += 1
            print(f"MISMATCH {where} [{name}]")
            print("  pyyaml :", str(want)[:300])
            print("  yamlish:", str(got)[:300])
    for text in BAD:
        n += 1
        try:
            yaml.safe_load(text)
            print("BAD case is valid YAML, fix the test:", repr(text)); fails += 1; continue
        except yaml.YAMLError:
            pass
        try:
            got = yamlish.load(text)
            fails += 1
            print("NOT REJECTED:", repr(text), "->", got)
        except yamlish.YamlError:
            pass
    print(f"{n - fails}/{n} blocks match")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
