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
    """SPEC-v2: `isa verify` ticks, so it applies the order — the model can't tick at all (test_commands)."""

    def test_dependent_pass_waits(self):
        path = self.write_isa(self.text)
        self.flag("ok3")
        rc, out = self.verify(path, "ISC-3")
        self.assertEqual(rc, 0, out)
        self.assertFalse(lint.parse(read(path))["iscs"]["ISC-3"][0])
        self.assertIn("ISC-3 passed but waits — Feature `B` depends on `A` (still open: ISC-1, ISC-2)", out)


class TestDependencyDone(OrderCase):
    def test_dependency_and_dependent_in_one_run(self):
        path = self.write_isa(self.text)
        for n in (1, 2, 3):
            self.flag(f"ok{n}")
        rc, out = self.verify(path, "ISC-3", "ISC-1", "ISC-2")  # listed out of order on purpose
        self.assertEqual(rc, 0, out)
        iscs = lint.parse(read(path))["iscs"]
        self.assertTrue(all(iscs[i][0] for i in ("ISC-1", "ISC-2", "ISC-3")))

    def test_waiting_pass_ticked_by_a_later_run(self):
        path = self.write_isa(self.text)
        for n in (1, 2, 3):
            self.flag(f"ok{n}")
        self.verify(path, "ISC-3")
        self.verify(path, "ISC-1", "ISC-2")
        self.assertFalse(lint.parse(read(path))["iscs"]["ISC-3"][0])  # a tick needs its own run
        self.verify(path, "ISC-3")
        self.assertTrue(lint.parse(read(path))["iscs"]["ISC-3"][0])


class TestUnconstrained(OrderCase):
    def test_independent_feature_and_featureless_isc_tick_while_a_is_open(self):
        path = self.write_isa(self.text)
        self.flag("ok4")
        self.flag("ok5")
        self.verify(path, "ISC-4", "ISC-5")
        iscs = lint.parse(read(path))["iscs"]
        self.assertTrue(iscs["ISC-4"][0] and iscs["ISC-5"][0])

    def test_first_feature_ticks_freely(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.verify(path, "ISC-1")
        self.assertTrue(lint.parse(read(path))["iscs"]["ISC-1"][0])

    def test_isa_without_features(self):
        path = self.write_isa(self.text.split("\n## Features")[0] + "\n")
        self.flag("ok3")
        self.verify(path, "ISC-3")
        self.assertTrue(lint.parse(read(path))["iscs"]["ISC-3"][0])


class TestNoDeadlock(OrderCase):
    def test_waiting_pass_does_not_freeze_work(self):
        path = self.write_isa(self.text)
        self.flag("ok3")
        rc, out = self.verify(path, "ISC-3")
        self.assertEqual(rc, 0)
        self.assertIn("ISC-3 passed but waits", out)
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
