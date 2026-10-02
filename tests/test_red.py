"""SPEC-v2 M5: red-then-green. A behaviour/http/schema ISC at E2+ is ticked plainly only after its probe,
as written now, was seen failing (`isa verify --red`) on a different tree; otherwise it is ticked with
`(no red baseline)` and listed at close. Nothing is ever blocked for lack of a baseline.

Run: python3 -m unittest tests.test_red
"""
import os
import sys
import unittest

from tests.test_evidence import read
from tests.test_fingerprint import GitCommandCase
from tests.test_hooks import ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import commands, evidence, isafile, lint  # noqa: E402

RED_ISA = """---
task: "Red fixture"
slug: 20260101-000000_t
effort: E2
phase: build
progress: 0/3
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
---

## Problem

A fixture for red-then-green.

## Goal

`add` exists and returns the sum.

## Criteria

- [ ] ISC-1: `add(2, 3)` returns 5.
- [ ] ISC-2: `calc.py` exists.
- [ ] ISC-3: Anti: nothing else breaks.

## Test Strategy

```yaml
- isc: ISC-1
  type: unit-test
  kind: behaviour
  check: unit test
  threshold: exit 0
  tool: python3 test_calc.py
- isc: ISC-2
  type: bash
  kind: file
  check: file exists
  threshold: exit 0
  tool: test -f calc.py
- isc: ISC-3
  type: bash
  kind: behaviour
  check: anti
  threshold: exit 0
  tool: "true"
```
"""
TEST = "import unittest\nfrom calc import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n" \
       "        self.assertEqual(add(2, 3), 5)\n\nunittest.main()\n"
WEAK_TEST = "import unittest\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        pass\n\nunittest.main()\n"
CALC = "def add(a, b):\n    return a + b\n"


class RedCase(GitCommandCase):
    def put(self, rel, text):
        with open(os.path.join(self.proj, rel), "w") as f:
            f.write(text)

    def line(self, path, isc):
        return isafile.generated_lines(read(path)).get(isc, "")

    def closeable(self, path):
        self.verify(path)
        self.write_isa(read(path).rstrip("\n") + "\n- Goal: yes — done\n", path)
        return self.isa("close", path)


class TestBaselineTick(RedCase):
    def test_red_then_green(self):
        path = self.write_isa(RED_ISA)
        self.put("test_calc.py", TEST)
        rc, out = self.isa("verify", "--red", path, "ISC-1")
        self.assertEqual(rc, 0, out)
        self.assertIn("ISC-1 FAIL (red, as expected)", out)
        self.assertFalse(lint.parse(read(path))["iscs"]["ISC-1"][0])  # red never ticks
        self.put("calc.py", CALC)
        rc, out = self.verify(path, "ISC-1")
        self.assertEqual(rc, 0, out)
        self.assertTrue(lint.parse(read(path))["iscs"]["ISC-1"][0])
        self.assertNotIn("no red baseline", self.line(path, "ISC-1"))


class TestWeakenedProbe(RedCase):
    def test_probe_text_changed_after_red(self):
        path = self.write_isa(RED_ISA)
        self.put("test_calc.py", TEST)
        self.isa("verify", "--red", path, "ISC-1")
        self.put("calc.py", CALC)
        self.write_isa(read(path).replace("tool: python3 test_calc.py", "tool: python3 test_calc.py || true"), path)
        rc, out = self.verify(path, "ISC-1")
        self.assertEqual(rc, 0, out)
        self.assertIn("(no red baseline)", self.line(path, "ISC-1"))
        self.assertIn("edited after its failing red run", out)


class TestCantFail(RedCase):
    def test_true_probe(self):
        text = RED_ISA.replace("tool: python3 test_calc.py", 'tool: "true"')
        path = self.write_isa(text)
        rc, out = self.isa("verify", "--red", path, "ISC-1")
        self.assertIn("already green before the change", out)
        rc, out = self.isa("lint", path)
        self.assertEqual(rc, 0, out)  # a warning, never an error
        self.assertIn("WARN: ISC-1: its probe passed its red run", out)
        self.put("calc.py", CALC)
        self.verify(path, "ISC-1")
        self.assertIn("(no red baseline)", self.line(path, "ISC-1"))


class TestWeakenedTestFile(RedCase):
    def test_baseline_kept_and_reported(self):
        path = self.write_isa(RED_ISA)
        self.put("test_calc.py", TEST)
        self.isa("verify", "--red", path, "ISC-1")
        self.put("test_calc.py", WEAK_TEST)  # the test itself weakened, same command
        self.put("calc.py", CALC)
        rc, out = self.closeable(path)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("no red baseline", self.line(path, "ISC-1"))
        self.assertIn("Changed since red", out)
        self.assertIn("ISC-1: test_calc.py", out)


class TestGrepOfNewText(RedCase):
    def test_accepted_known_limit(self):
        text = RED_ISA.replace("tool: python3 test_calc.py",
                               "tool: python3 -c \"print(open('calc.py').read())\" | grep -q 'def add'")
        path = self.write_isa(text)
        self.assertEqual(lint.parse(read(path))["test_strategy"]["ISC-1"]["tool"],
                         "python3 -c \"print(open('calc.py').read())\" | grep -q 'def add'")
        rc, out = self.isa("verify", "--red", path, "ISC-1")
        self.assertIn("ISC-1 FAIL (red, as expected)", out)
        self.put("calc.py", CALC)
        rc, out = self.verify(path, "ISC-1")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("no red baseline", self.line(path, "ISC-1"))  # red before, green after: it passes


class TestExempt(RedCase):
    def test_exemptions(self):
        p = lint.parse(RED_ISA)
        self.assertEqual(commands.red_exempt(p, "ISC-3"), "Anti")
        self.assertEqual(commands.red_exempt(p, "ISC-2"), "kind file")
        self.assertIsNone(commands.red_exempt(p, "ISC-1"))
        reg = lint.parse(RED_ISA.replace("  kind: behaviour\n  check: unit test", "  kind: regression\n  check: unit test"))
        self.assertEqual(commands.red_exempt(reg, "ISC-1"), "regression")
        ex = lint.parse(RED_ISA.replace("  kind: behaviour\n  check: unit test",
                                        "  kind: behaviour\n  red: exempt — the API is live only\n  check: unit test"))
        self.assertEqual(commands.red_exempt(ex, "ISC-1"), "exempt — the API is live only")
        self.assertEqual(commands.red_exempt(lint.parse(RED_ISA.replace("effort: E2", "effort: E1")), "ISC-1"), "E1")

    def test_anti_ticks_plainly(self):
        path = self.write_isa(RED_ISA)
        self.verify(path, "ISC-3")
        self.assertTrue(lint.parse(read(path))["iscs"]["ISC-3"][0])
        self.assertNotIn("no red baseline", self.line(path, "ISC-3"))


class TestCloseLists(RedCase):
    def test_summary(self):
        text = RED_ISA.replace("  kind: file\n  check: file exists",
                               "  kind: behaviour\n  red: exempt — created by the build\n  check: file exists")
        path = self.write_isa(text)
        self.put("test_calc.py", TEST)
        self.put("calc.py", CALC)  # implemented with no red run at all
        rc, out = self.closeable(path)
        self.assertEqual(rc, 0, out)
        self.assertIn("No red baseline", out)
        self.assertIn("ISC-1: no `isa verify --red` run of it before the change", out)
        self.assertIn("Red run exempted by the ISA: ISC-2 (exempt — created by the build)", out)


class TestNeverBlocks(RedCase):
    def test_no_gate_and_tick_lands(self):
        path = self.write_isa(RED_ISA)
        out = self.hook("PreToolUse", tool_name="Write",
                        tool_input={"file_path": os.path.join(self.proj, "calc.py"), "content": CALC})[1]
        self.assertIsNone(self.decision(out))  # no red-baseline gate on the first change
        self.put("test_calc.py", TEST)
        self.put("calc.py", CALC)
        rc, out = self.verify(path, "ISC-1")
        self.assertEqual(rc, 0, out)
        self.assertTrue(lint.parse(read(path))["iscs"]["ISC-1"][0])
        self.assertIn("(no red baseline)", self.line(path, "ISC-1"))


class TestNamedFiles(RedCase):
    def test_files_field(self):
        path = self.write_isa(RED_ISA)
        self.put("test_calc.py", TEST)
        self.put("calc.py", CALC)
        self.verify(path, "ISC-1")
        [row] = [r for r in evidence.rows(path) if r.get("kind") == "verify"]
        self.assertEqual(list(row["files"]), ["test_calc.py"])
        self.assertTrue(row["files"]["test_calc.py"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
