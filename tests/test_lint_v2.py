"""SPEC-v2 M6: the lint and close rules of § 6 and the SHAPE rows of § 2.

Run: python3 -m unittest tests.test_lint_v2
"""
import json
import os
import sys
import unittest

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_hooks import fake_cli
from tests.test_hooks import ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence, lint  # noqa: E402

V2 = """---
task: "v2 fixture"
slug: 20261002-100000_t
effort: E2
phase: build
progress: 0/3
started: 2026-10-02T10:00:00Z
updated: 2026-10-02T10:00:00Z
context_sufficient: true
---

## Problem

A fixture for the v2 lint rules.

## Goal

Every rule fires where it should.

## Criteria

- [ ] ISC-1: the parser handles empty input.
- [ ] ISC-2: the output file lists every entry.
- [ ] ISC-3: Anti: no existing test breaks.

## Test Strategy

```yaml
- isc: ISC-1
  type: unit-test
  kind: behaviour
  check: unit
  threshold: exit 0
  tool: python3 -m unittest -q tests.test_parse
- isc: ISC-2
  type: bash
  kind: file
  check: grep
  threshold: exit 0
  tool: grep -q entry out.txt
  fails-when: "out.txt has no entry line"
- isc: ISC-3
  type: bash
  kind: regression
  check: suite
  threshold: exit 0
  tool: python3 -m unittest -q
  fails-when: "any existing test fails"
```
"""
PRE_V2 = V2.replace("started: 2026-10-02T10:00:00Z", "started: 2026-09-01T10:00:00Z")


def items(text, moment="articulation"):
    r = lint.lint("ISA.md", moment, text=text)
    return [m for lvl, m in r.items if lvl == "ERROR"], [m for lvl, m in r.items if lvl == "WARN"]


def closed(text, extra_ver=""):
    """The fixture with every ISC ticked, complete, a Verification line each and a Goal line."""
    for i in ("ISC-1", "ISC-2", "ISC-3"):
        text = text.replace(f"- [ ] {i}:", f"- [x] {i}:")
    text = text.replace("phase: build", "phase: complete").replace("progress: 0/3", "progress: 3/3")
    return text.rstrip("\n") + ("\n\n## Verification\n\n- ISC-1: verified 2026-10-02T10:00:00 — exit 0 in 0s — `x`\n"
                                "- ISC-2: verified 2026-10-02T10:00:00 — exit 0 in 0s — `x`\n"
                                "- ISC-3: verified 2026-10-02T10:00:00 — exit 0 in 0s — `x`\n" + extra_ver +
                                "- Goal: yes — done\n")


class TestKindRequired(unittest.TestCase):
    def test_by_tier_and_date(self):
        no_kind = V2.replace("  kind: file\n", "")
        errs, _ = items(no_kind)
        self.assertTrue(any("ISC-2 missing `kind:`" in e for e in errs), errs)
        errs, warns = items(no_kind.replace("started: 2026-10-02T10:00:00Z", "started: 2026-09-01T10:00:00Z"))
        self.assertFalse(any("kind" in e for e in errs))
        self.assertTrue(any("ISC-2 missing `kind:`" in w for w in warns))
        errs, warns = items(no_kind.replace("effort: E2", "effort: E1"))
        self.assertFalse(any("kind" in e for e in errs))
        self.assertTrue(any("missing `kind:`" in w for w in warns))
        errs, _ = items(V2.replace("kind: file", "kind: vibes"))
        self.assertTrue(any("`kind: vibes` is not one of" in e for e in errs))
        self.assertEqual(items(V2)[0], [])


class TestContextSufficient(unittest.TestCase):
    def test_rule_6(self):
        without = V2.replace("context_sufficient: true\n", "")
        self.assertTrue(any("`context_sufficient` not set" in e for e in items(without)[0]))
        self.assertEqual(items(V2.replace("context_sufficient: true", "context_sufficient: false"))[0], [])
        errs, warns = items(without.replace("started: 2026-10-02T10:00:00Z", "started: 2026-09-01T10:00:00Z"))
        self.assertFalse(any("context_sufficient" in e for e in errs))
        self.assertTrue(any("context_sufficient" in w for w in warns))
        self.assertFalse(any("context_sufficient" in e for e in items(without.replace("effort: E2", "effort: E1"))[0]))


class TestKindTable(unittest.TestCase):
    def test_refusals(self):
        errs, _ = items(V2.replace("  type: unit-test\n  kind: behaviour", "  type: manual\n  kind: behaviour"))
        self.assertTrue(any("`kind: behaviour` can't be proven by a `manual` probe" in e for e in errs), errs)
        errs, _ = items(V2.replace("tool: python3 -m unittest -q tests.test_parse", "tool: grep -q 'def parse' p.py"))
        self.assertTrue(any("grep-only" in e for e in errs), errs)
        errs, _ = items(V2.replace("tool: python3 -m unittest -q tests.test_parse",
                                   "tool: python3 p.py '' | grep -q empty"))
        self.assertEqual(errs, [])  # runs the code, then greps its output
        errs, _ = items(V2.replace("  type: bash\n  kind: regression", "  type: manual\n  kind: regression"))
        self.assertTrue(any("`kind: regression` can't be proven by a `manual`" in e for e in errs), errs)
        ok = V2.replace("  type: bash\n  kind: file\n  check: grep", "  type: manual\n  kind: decision\n  check: grep")
        self.assertEqual(items(ok)[0], [])

    def test_grep_only_table(self):
        for tool, want in [("grep -q x f", True), ("test -f a && grep -q b a", True), ("cat f | wc -l", True),
                           ("! grep -q TODO src/x.py", True), ("cd sub && rg -q x", True),
                           ("python3 x.py | grep -q y", False), ("pytest -q", False), ("", False),
                           ('test "$(./app --help | wc -l)" -le 12', False), ('test "$(cat f | wc -l)" -eq 3', True),
                           ("test `./app --version` = 1.0", False),
                           ('test "$(./app $(cat ids.txt) | wc -c)" -eq 0', False)]:
            self.assertEqual(lint.grep_only(tool), want, tool)


class TestRiskDeclared(unittest.TestCase):
    TOKEN = V2.replace("ISC-2: the output file lists every entry.", "ISC-2: the deploy token is rotated.")

    def test_declaration(self):
        e3 = self.TOKEN.replace("effort: E2", "effort: E3")
        errs, _ = items(e3)
        self.assertTrue(any("ISC-2 mentions `deploy`" in e for e in errs), errs)
        errs, warns = items(self.TOKEN)  # E2: a warning
        self.assertFalse(any("mentions" in e for e in errs))
        self.assertTrue(any("ISC-2 mentions" in w for w in warns))
        errs, _ = items(e3.replace("  kind: file\n", "  kind: file\n  risk: low\n"))
        self.assertTrue(any("`risk: low` needs its reason" in e for e in errs), errs)
        errs, _ = items(e3.replace("  kind: file\n", "  kind: file\n  risk: low — a staging token, rotated daily\n"))
        self.assertFalse(any("risk" in e for e in errs), errs)
        errs, _ = items(e3.replace("  kind: file\n", "  kind: file\n  risk: medium\n"))
        self.assertTrue(any("`risk:` must be `high` or `low — <why>`" in e for e in errs), errs)


class TestRiskHigh(unittest.TestCase):
    def test_self_attested_refused_unless_waived(self):
        high = V2.replace("  type: bash\n  kind: file\n", "  type: manual\n  kind: decision\n  risk: high\n")
        errs, _ = items(high)
        self.assertTrue(any("ISC-2 is `risk: high` — a `manual` probe can't prove it" in e for e in errs), errs)
        waived = high + '\n## Decisions\n\n- 2026-10-02 10:00: waived: ISC-2 — "skip the token check"\n'
        self.assertFalse(any("risk: high" in e for e in items(waived)[0]))
        self.assertEqual(items(V2.replace("  kind: file\n", "  kind: file\n  risk: high\n"))[0], [])


class RulesCase(CommandCase):
    def setUp(self):
        super().setUp()
        self.flag("ok")

    def lint_out(self, path):
        return self.isa("lint", path)


class TestDowngrade(RulesCase):
    def test_snapshot_and_failing_run(self):
        text = V2.replace("tool: grep -q entry out.txt", f"tool: test -f {self.d}/nope")
        path = self.write_isa(text)
        self.verify(path, "ISC-2")  # takes the strategy snapshot; the probe fails
        down = read(path).replace(f"  type: bash\n  kind: file\n  check: grep\n  threshold: exit 0\n"
                                  f"  tool: test -f {self.d}/nope", "  type: manual\n  kind: decision\n"
                                  "  check: grep\n  threshold: exit 0\n  tool: look at it")
        self.write_isa(down, path)
        rc, out = self.lint_out(path)
        self.assertEqual(rc, 1, out)
        self.assertIn("ISC-2 probe downgraded", out)
        rc, out = self.isa("verify", path, "ISC-2", "--attest", "looks fine")
        self.assertEqual(rc, 1, out)  # can't attest around it either: articulation fails first
        self.write_isa(read(path).rstrip("\n") + "\n\n## Decisions\n\n- 2026-10-02 10:00: refined: ISC-2 probe "
                                                  "downgraded — the file is produced by hand now\n", path)
        rc, out = self.lint_out(path)
        self.assertNotIn("probe downgraded", out)

    def test_kind_weakened(self):
        path = self.write_isa(V2)
        self.verify(path, "ISC-2")
        self.write_isa(read(path).replace("  type: unit-test\n  kind: behaviour", "  type: unit-test\n  kind: doc"), path)
        rc, out = self.lint_out(path)
        self.assertIn("`kind:` weakened from `behaviour` to `doc`", out)


class TestWaiverQuote(RulesCase):
    def test_quote_from_session(self):
        self.hook("UserPromptSubmit", prompt="please waive ISC-2, the staging box is gone for good")
        path = self.write_isa(V2)
        good = V2 + '\n## Decisions\n\n- 2026-10-02 10:00: waived: ISC-2 — "the staging box is gone for good"\n'
        self.write_isa(good, path)
        rc, out = self.lint_out(path)
        self.assertNotIn("waived", out)
        self.write_isa(good.replace("the staging box is gone for good", "the user said skip it"), path)
        rc, out = self.lint_out(path)
        self.assertIn("is not in any prompt of this ISA's sessions", out)
        self.write_isa(V2 + "\n## Decisions\n\n- 2026-10-02 10:00: waived: ISC-2 — not needed\n", path)
        rc, out = self.lint_out(path)
        self.assertIn("must quote the user", out)

    def test_pre_v2_warns(self):
        path = self.write_isa(PRE_V2 + "\n## Decisions\n\n- 2026-09-01 10:00: waived: ISC-2 — not needed\n")
        rc, out = self.lint_out(path)
        self.assertEqual(rc, 0, out)
        self.assertIn("WARN: Decisions: `waived: ISC-2` must quote the user", out)


class TestSecondLook(unittest.TestCase):
    def test_rows(self):
        e4 = closed(V2.replace("effort: E2", "effort: E4"))
        errs, _ = items(e4, "close")
        self.assertTrue(any("no `second-look:" in e for e in errs), errs)
        high = closed(V2.replace("  kind: file\n", "  kind: file\n  risk: high\n"))
        self.assertTrue(any("no `second-look:" in e for e in items(high, "close")[0]))
        fixed = high.replace("## Verification", "## Decisions\n\n- 2026-10-02 10:00: second-look: a fresh-context "
                                                "reviewer read the diff — no findings\n\n## Verification")
        self.assertFalse(any("second-look" in e for e in items(fixed, "close")[0]))
        bad = V2 + "\n## Decisions\n\n- 2026-10-02 10:00: finding: the retry loop never ends — fixed it\n"
        self.assertTrue(any("malformed `finding:` row" in e for e in items(bad)[0]))
        good = V2 + "\n## Decisions\n\n- 2026-10-02 10:00: finding: the retry loop never ends — adopted (ISC-4)\n"
        self.assertEqual(items(good)[0], [])


class TestAsks(RulesCase):
    PROMPT = "Review utils.py for bugs and list each one with its line number. Do not change any files."

    def test_ask_lines_at_close(self):
        asked = V2.replace("updated: 2026-10-02T10:00:00Z", 'updated: 2026-10-02T10:00:00Z\nasks: ["list each bug", '
                                                            '"do not change files"]')
        errs, _ = items(closed(asked), "close")
        self.assertTrue(any("ask 1 (\"list each bug\") has no `- Ask 1:" in e for e in errs), errs)
        ok = closed(asked, "- Ask 1: met — every bug listed\n- Ask 2: met — git status is clean\n")
        self.assertFalse(any("Ask" in e for e in items(ok, "close")[0]))
        skipped = closed(asked, "- Ask 1: met — listed\n- Ask 2: skipped\n")
        self.assertTrue(any("`- Ask 2: skipped` needs its reason" in e for e in items(skipped, "close")[0]))

    def test_removal_needs_refined_row(self):
        path = self.write_isa(V2.replace("updated: 2026-10-02T10:00:00Z",
                                         'updated: 2026-10-02T10:00:00Z\nasks: ["list each bug"]'))
        evidence.record(path, [{"v": 2, "t": 1.0, "kind": "asks", "asks": ["list each bug", "do not change files"]}])
        rc, out = self.lint_out(path)
        self.assertIn("ask removed from `asks:` without a `refined:`", out)
        self.write_isa(read(path).rstrip("\n") + "\n\n## Decisions\n\n- 2026-10-02 10:00: refined: ask 2 dropped — "
                                                  "the user withdrew it\n", path)
        rc, out = self.lint_out(path)
        self.assertNotIn("ask removed", out)


class TestFailsWhen(unittest.TestCase):
    """SPEC-v2 § 11.2: from E2, a mechanical probe whose ISC can't get a red baseline (Anti, a kind without
    the red step, `red: exempt`) says what it sees when the claim is false."""

    def test_required_on_red_exempt_entries(self):
        bare = V2.replace('  fails-when: "out.txt has no entry line"\n', "").replace(
            '  fails-when: "any existing test fails"\n', "")
        errs, _ = items(bare)
        self.assertTrue(any("ISC-2 can't get a red baseline (kind file)" in e for e in errs), errs)
        self.assertTrue(any("ISC-3 can't get a red baseline (Anti)" in e for e in errs), errs)
        self.assertFalse(any("ISC-1 can't get a red baseline" in e for e in errs), errs)  # behaviour: red-then-green
        self.assertEqual(items(V2)[0], [])

    def test_red_exempt_and_not_for_self_attested_or_e1(self):
        exempt = V2.replace("  kind: behaviour\n", "  kind: behaviour\n  red: exempt — pure refactor\n")
        self.assertTrue(any("ISC-1 can't get a red baseline (exempt — pure refactor)" in e for e in items(exempt)[0]))
        manual = V2.replace('  tool: grep -q entry out.txt\n  fails-when: "out.txt has no entry line"\n',
                            "  tool: open out.txt and read it\n").replace("  type: bash\n  kind: file", "  type: manual\n  kind: file")
        self.assertFalse(any("ISC-2 can't get a red baseline" in e for e in items(manual)[0]))
        e1 = V2.replace("effort: E2", "effort: E1").replace('  fails-when: "any existing test fails"\n', "")
        self.assertFalse(any("can't get a red baseline" in e for e in items(e1)[0]))

    def test_older_isas_get_a_warning(self):
        bare = PRE_V2.replace('  fails-when: "out.txt has no entry line"\n', "")
        errs, warns = items(bare)
        self.assertFalse(any("red baseline" in e for e in errs), errs)
        self.assertTrue(any("ISC-2 can't get a red baseline" in w for w in warns), warns)


class TestShapeRows(unittest.TestCase):
    def test_class_sweep(self):
        tagged = closed(V2.replace("  kind: behaviour\n", "  kind: behaviour\n  class: empty-input crash\n"))
        errs, _ = items(tagged, "close")
        self.assertTrue(any("`class: empty-input crash` needs a `class-sweep:" in e for e in errs), errs)
        swept = tagged.replace("## Verification", "## Decisions\n\n- 2026-10-02 10:00: class-sweep: empty-input "
                                                  "crash — 3 siblings via rg -n 'parse('; 3 fixed, 0 tombstoned\n\n"
                                                  "## Verification")
        self.assertFalse(any("class-sweep" in e for e in items(swept, "close")[0]))

    def test_repro_bypass(self):
        bad = V2 + "\n## Decisions\n\n- 2026-10-02 10:00: repro-bypass: too hard to reproduce\n"
        self.assertTrue(any("malformed `repro-bypass:` row" in e for e in items(bad)[0]))
        good = V2 + "\n## Decisions\n\n- 2026-10-02 10:00: repro-bypass: pure-additive — a new flag, no bug\n"
        self.assertEqual(items(good)[0], [])


if __name__ == "__main__":
    unittest.main()
