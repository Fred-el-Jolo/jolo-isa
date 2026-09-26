"""Feature dependency order: an ISC can't be ticked before the Features its Feature depends on are done.

Run: python3 -m unittest tests.test_feature_order
"""
import os
import unittest

from tests.test_evidence import GateCase, read
from tests.test_hooks import ROOT
from isa import lint

FIXTURE = """---
task: "Feature order fixture"
slug: 20260101-000000_t
effort: E2
phase: build
progress: 0/5
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
---

## Problem

A fixture for Feature dependency order.

## Goal

Dependent Features are ticked only after their dependencies.

## Criteria

- [ ] ISC-1: first step of A.
- [ ] ISC-2: second step of A.
- [ ] ISC-3: B, which needs A.
- [ ] ISC-4: C, independent.
- [ ] ISC-5: Anti: belongs to no Feature.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: flag
  threshold: exit 0
  tool: test -f {d}/ok1
- isc: ISC-2
  type: bash
  check: flag
  threshold: exit 0
  tool: test -f {d}/ok2
- isc: ISC-3
  type: bash
  check: flag
  threshold: exit 0
  tool: test -f {d}/ok3
- isc: ISC-4
  type: bash
  check: flag
  threshold: exit 0
  tool: test -f {d}/ok4
- isc: ISC-5
  type: bash
  check: flag
  threshold: exit 0
  tool: test -f {d}/ok5
```

## Features

```yaml
- name: A
  description: the base
  satisfies: [ISC-1, ISC-2]
  depends_on: []
  parallelizable: false
- name: B
  description: built on A
  satisfies: [ISC-3]
  depends_on: [A]
  parallelizable: false
- name: C
  description: independent
  satisfies: [ISC-4]
  depends_on: []
  parallelizable: true
```
"""


def tick(text, *iscs):
    for i in iscs:
        text = text.replace(f"- [ ] {i}:", f"- [x] {i}:")
    return text.replace("progress: 0/5", f"progress: {text.count('- [x] ISC-')}/5")


class OrderCase(GateCase):
    def setUp(self):
        super().setUp()
        self.text = FIXTURE.replace("{d}", self.d)


def errors(text):
    return [m for lvl, m in lint.lint("ISA.md", "articulation", text=text).items if lvl == "ERROR"]


class TestDependencyLint(unittest.TestCase):
    def test_fixture_is_clean(self):
        self.assertEqual(errors(FIXTURE.replace("{d}", "/x")), [])

    def test_unknown_dependency(self):
        text = FIXTURE.replace("{d}", "/x").replace("depends_on: [A]", "depends_on: [Nope]")
        self.assertIn("Features: `B` depends on unknown Feature `Nope`", errors(text))

    def test_cycle(self):
        text = FIXTURE.replace("{d}", "/x").replace(
            "  satisfies: [ISC-1, ISC-2]\n  depends_on: []", "  satisfies: [ISC-1, ISC-2]\n  depends_on: [B]")
        self.assertTrue(any("dependency cycle" in e and "A" in e and "B" in e for e in errors(text)), errors(text))

    def test_examples_with_dependencies_have_no_cycle(self):
        for name in sorted(os.listdir(os.path.join(ROOT, "skill/ISA/Examples"))):
            text = read(os.path.join(ROOT, "skill/ISA/Examples", name))
            self.assertFalse([e for e in errors(text) if "depends on" in e or "cycle" in e], name)



class TestBlockedTick(OrderCase):
    def test_tick_of_dependent_feature_refused(self):
        path = self.write_isa(self.text)
        self.flag("ok3")
        self.verify(path, "ISC-3")
        out = self.pre("Edit", file_path=path, old_string="- [ ] ISC-3:", new_string="- [x] ISC-3:")
        self.assertEqual(self.decision(out), "deny")
        reason = self.reason(out)
        self.assertIn("ISC-3 belongs to Feature `B`, which depends on `A`", reason)
        self.assertIn("still open in `A`: ISC-1, ISC-2", reason)



class TestDependencyDone(OrderCase):
    def setUp(self):
        super().setUp()
        self.path = self.write_isa(self.text)
        for n in (1, 2, 3):
            self.flag(f"ok{n}")
        self.verify(self.path, "ISC-1", "ISC-2", "ISC-3")

    def test_dependency_and_dependent_in_one_edit_refused(self):
        out = self.pre("Write", file_path=self.path, content=tick(self.text, "ISC-1", "ISC-2", "ISC-3"))
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("ISC-3 belongs to Feature `B`", self.reason(out))

    def test_allowed_after_dependency_ticked_earlier(self):
        self.assertIsNone(self.decision(self.pre("Write", file_path=self.path,
                                                 content=tick(self.text, "ISC-1", "ISC-2"))))
        self.write_isa(tick(self.text, "ISC-1", "ISC-2"), self.path)
        out = self.pre("Edit", file_path=self.path, old_string="- [ ] ISC-3:", new_string="- [x] ISC-3:")
        self.assertIsNone(self.decision(out))



class TestUnconstrained(OrderCase):
    def test_independent_feature_and_featureless_isc_tick_while_a_is_open(self):
        path = self.write_isa(self.text)
        self.flag("ok4")
        self.flag("ok5")
        self.verify(path, "ISC-4", "ISC-5")
        self.assertIsNone(self.decision(self.pre("Write", file_path=path, content=tick(self.text, "ISC-4", "ISC-5"))))

    def test_first_feature_ticks_freely(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.verify(path, "ISC-1")
        self.assertIsNone(self.decision(self.pre("Write", file_path=path, content=tick(self.text, "ISC-1"))))

    def test_isa_without_features(self):
        path = self.write_isa(self.text.split("\n## Features")[0] + "\n")
        self.flag("ok3")
        self.verify(path, "ISC-3")
        text = read(path)
        self.assertIsNone(self.decision(self.pre("Write", file_path=path, content=tick(text, "ISC-3"))))



class TestNoDeadlock(OrderCase):
    def test_blocked_pass_does_not_freeze_work(self):
        path = self.write_isa(self.text)
        self.flag("ok3")
        rc, out = self.verify(path, "ISC-3")
        self.assertEqual(rc, 0)
        self.assertIn("ISC-3 blocked", out)
        self.assertNotIn("Passed and not ticked yet", out)
        project_write = self.pre("Write", file_path=os.path.join(self.proj, "y.py"), content="y")
        self.assertIsNone(self.decision(project_write))
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 0)



class TestShellOutOfOrder(OrderCase):
    def test_shell_tick_out_of_order_reported_and_blocks_stop(self):
        path = self.write_isa(self.text)
        self.flag("ok3")
        self.verify(path, "ISC-3")
        out = self.shell_edit(path, tick(self.text, "ISC-3"))
        self.assertIn("out of dependency order", self.ctx(out))
        self.assertIn("ISC-3 belongs to Feature `B`", self.ctx(out))
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("out of dependency order", err)


if __name__ == "__main__":
    unittest.main()
