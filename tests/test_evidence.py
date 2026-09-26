"""Evidence-gated ticks: `isa verify`, the ledger, and the hooks that refuse unproven ticks.

Run: python3 -m unittest tests.test_evidence
"""
import json
import os
import subprocess
import sys
import time
import unittest

from tests.test_hooks import ISA, ROOT, HookCase

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence, lint  # noqa: E402

FIXTURE = """---
task: "Evidence fixture"
slug: 20260101-000000_t
effort: E2
phase: build
progress: 0/4
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
---

## Problem

A fixture for evidence-gated ticks.

## Goal

Probes decide which ISCs may be ticked.

## Criteria

- [ ] ISC-1: first probe passes.
- [ ] ISC-2: second probe passes.
- [ ] ISC-3: checked by hand.
- [ ] ISC-4: Anti: shares the first probe.

## Test Strategy

```yaml
- isc: ISC-1
  type: bash
  check: flag file one
  threshold: exit 0
  tool: echo run >> {d}/runs && test -f {d}/ok1
- isc: ISC-2
  type: bash
  check: flag file two
  threshold: exit 0
  tool: test -f {d}/ok2
- isc: ISC-3
  type: manual
  check: look at it
  threshold: looks right
  tool: read the output
- isc: ISC-4
  type: bash
  check: same probe as ISC-1
  threshold: exit 0
  tool: echo run >> {d}/runs && test -f {d}/ok1
```
"""


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def tick(text, *iscs):
    for i in iscs:
        text = text.replace(f"- [ ] {i}:", f"- [x] {i}:")
    n = text.count("- [x] ISC-")
    return text.replace("progress: 0/4", f"progress: {n}/4")


class EvidenceCase(HookCase):
    def setUp(self):
        super().setUp()
        self.d = os.path.join(self.tmp, "flags")
        os.makedirs(self.d)
        self.text = FIXTURE.replace("{d}", self.d)
        self._env = os.environ.get("ISA_HOME")
        os.environ["ISA_HOME"] = self.home  # for in-process evidence.* calls

    def tearDown(self):
        if self._env is None:
            os.environ.pop("ISA_HOME", None)
        else:
            os.environ["ISA_HOME"] = self._env
        super().tearDown()

    def flag(self, name, on=True):
        p = os.path.join(self.d, name)
        if on:
            open(p, "w").close()
        elif os.path.exists(p):
            os.remove(p)

    def verify(self, path, *iscs):
        p = subprocess.run([sys.executable, ISA, "verify", path, *iscs], cwd=self.proj, env=self.env,
                           text=True, capture_output=True, timeout=60)
        return p.returncode, p.stdout + p.stderr

    def parsed(self, path):
        return lint.parse(read(path), path)

    def rows(self, path):
        try:
            return [json.loads(line) for line in read(evidence.ledger_path(path)).splitlines()]
        except OSError:
            return []


class TestVerifyRecords(EvidenceCase):
    def test_pass_records_and_exits_0(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        rc, out = self.verify(path, "ISC-1")
        self.assertEqual(rc, 0, out)
        self.assertIn("ISC-1 PASS", out)
        [row] = self.rows(path)
        tool = f"echo run >> {self.d}/runs && test -f {self.d}/ok1"
        self.assertEqual((row["isc"], row["ok"], row["exit"], row["tool_sha"]),
                         ("ISC-1", True, 0, evidence.tool_sha(tool)))

    def test_fail_records_and_exits_1(self):
        path = self.write_isa(self.text)
        rc, out = self.verify(path, "ISC-2")
        self.assertEqual(rc, 1)
        self.assertIn("ISC-2 FAIL", out)
        self.assertFalse(self.rows(path)[-1]["ok"])

    def test_default_runs_every_mechanical_probe_once(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.flag("ok2")
        rc, out = self.verify(path)
        self.assertEqual(rc, 0, out)
        self.assertEqual(sorted(r["isc"] for r in self.rows(path)), ["ISC-1", "ISC-2", "ISC-4"])
        self.assertEqual(read(os.path.join(self.d, "runs")).count("run"), 1)  # shared probe ran once

    def test_unknown_isc_is_usage_error(self):
        path = self.write_isa(self.text)
        self.assertEqual(self.verify(path, "ISC-99")[0], 2)
        self.assertEqual(self.rows(path), [])


class TestInvalidation(EvidenceCase):
    def test_later_failure_voids_pass(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.verify(path, "ISC-1")
        self.assertEqual(evidence.status(path, self.parsed(path), "ISC-1"), "proven")
        self.flag("ok1", on=False)
        self.verify(path, "ISC-1")
        self.assertEqual(evidence.status(path, self.parsed(path), "ISC-1"), "failed")

    def test_edited_probe_voids_pass(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        with open(path, "w") as f:
            f.write(self.text.replace(f"tool: test -f {self.d}/ok2", f"tool: test -e {self.d}/ok2"))
        self.assertEqual(evidence.status(path, self.parsed(path), "ISC-2"), "changed")

    def test_stale_against_later_change(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        self.assertEqual(evidence.status(path, self.parsed(path), "ISC-2", since=time.time()), "stale")


class TestSelfAttested(EvidenceCase):
    def test_manual_is_skipped_not_run(self):
        path = self.write_isa(self.text)
        rc, out = self.verify(path, "ISC-3")
        self.assertEqual(rc, 0)
        self.assertIn("ISC-3 SKIP  manual — self-attested", out)
        self.assertEqual(self.rows(path), [])

    def test_ticked_manual_and_probe_less_iscs_are_self_attested(self):
        path = self.write_isa(tick(self.text, "ISC-3"))
        self.assertEqual(evidence.self_attested_ticks(self.parsed(path)), [("ISC-3", "manual")])
        e1 = read(os.path.join(ROOT, "skill/ISA/Examples/e1-minimal.md")).replace("- [ ] ISC-1:", "- [x] ISC-1:")
        p = lint.parse(e1)
        self.assertEqual([i for i, _ in evidence.self_attested_ticks(p)], ["ISC-1"])
        self.assertEqual(evidence.probes(p)["ISC-1"]["type"], "no probe")


class GateCase(EvidenceCase):
    def pre(self, tool, **ti):
        return self.hook("PreToolUse", tool_name=tool, tool_input=ti)[1]

    def reason(self, out):
        return (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")

    def shell_edit(self, path, text):
        st = os.stat(path)
        with open(path, "w") as f:
            f.write(text)
        os.utime(path, (st.st_atime, st.st_mtime + 1))
        return self.hook("PostToolUse", tool_name="Bash", tool_input={"command": f"sed -i s/x/y/ {path}"},
                         tool_response={})[1]

    def closed(self):
        return tick(self.text, "ISC-1", "ISC-2", "ISC-3", "ISC-4").replace("phase: build", "phase: complete") + (
            "\n## Verification\n\n- ISC-1: v\n- ISC-2: v\n- ISC-3: v\n- ISC-4: v\n- Goal: yes — fixture\n")


class TestTickGateDenies(GateCase):
    def test_write_ticking_never_run_probe(self):
        path = self.write_isa(self.text)
        out = self.pre("Write", file_path=path, content=tick(self.text, "ISC-2"))
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("ISC-2: never run through `isa verify`", self.reason(out))
        self.assertIn(f"isa verify", self.reason(out))

    def test_edit_ticking_failed_probe(self):
        path = self.write_isa(self.text)
        self.verify(path, "ISC-2")
        out = self.pre("Edit", file_path=path, old_string="- [ ] ISC-2:", new_string="- [x] ISC-2:")
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("ISC-2: its latest `isa verify` run failed", self.reason(out))

    def test_pass_older_than_last_project_change(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        time.sleep(0.01)
        self.post_edit_project()
        out = self.pre("Edit", file_path=path, old_string="- [ ] ISC-2:", new_string="- [x] ISC-2:")
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("older than the last project change", self.reason(out))

    def test_multiedit_and_pi_edit(self):
        path = self.write_isa(self.text)
        out = self.pre("MultiEdit", file_path=path, edits=[{"old_string": "- [ ] ISC-1:", "new_string": "- [x] ISC-1:"}])
        self.assertEqual(self.decision(out), "deny")
        out = self.pre("edit", path=path, edits=[{"oldText": "- [ ] ISC-4:", "newText": "- [x] ISC-4:"}])
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("ISC-4", self.reason(out))

    def test_new_isa_written_pre_ticked(self):
        other = self.isa_path("20260101-000001_other")
        out = self.pre("Write", file_path=other, content=tick(self.text, "ISC-1"))
        self.assertEqual(self.decision(out), "deny")


class TestTickGateAllows(GateCase):
    def test_fresh_pass_allows_tick(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        self.write_isa(self.text, path)  # an ISA edit in between changes nothing
        out = self.pre("Edit", file_path=path, old_string="- [ ] ISC-2:", new_string="- [x] ISC-2:")
        self.assertIsNone(self.decision(out))

    def test_self_attested_and_untick_allowed(self):
        path = self.write_isa(self.text)
        self.assertIsNone(self.decision(self.pre("Write", file_path=path, content=tick(self.text, "ISC-3"))))
        self.assertIsNone(self.decision(self.pre("Write", file_path=path, content=self.text)))


class TestShellTick(GateCase):
    def test_shell_tick_reported_and_blocks_stop(self):
        path = self.write_isa(self.text)
        out = self.shell_edit(path, tick(self.text, "ISC-2"))
        self.assertIn("ticked without a passing `isa verify` run", self.ctx(out))
        self.assertIn("ISC-2", self.ctx(out))
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("verify or untick", err)


class TestVerifiedUntickedNudge(GateCase):
    def test_verify_output_and_hook_context(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        rc, out = self.verify(path, "ISC-2")
        self.assertEqual(rc, 0)
        self.assertIn("Passed and not ticked yet", out)
        self.assertIn("- ISC-2: `isa verify` PASS", out)
        hook_out = self.hook("PostToolUse", tool_name="Bash", tool_input={"command": f"isa verify {path} ISC-2"},
                             tool_response={})[1]
        self.assertIn("Passed `isa verify`, not ticked yet: ISC-2", self.ctx(hook_out))


class TestPendingTickBlocksWork(GateCase):
    def test_project_change_refused_until_ticked(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        out = self.pre("Write", file_path=os.path.join(self.proj, "y.py"), content="y")
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("ISC-2 passed `isa verify` but is not ticked", self.reason(out))
        self.assertIsNone(self.decision(self.pre("Bash", command=f"isa verify {path} ISC-1")))
        tick_edit = dict(file_path=path, old_string="- [ ] ISC-2:", new_string="- [x] ISC-2:")
        self.assertIsNone(self.decision(self.pre("Edit", **tick_edit)))
        self.write_isa(tick(self.text, "ISC-2"), path)
        self.assertIsNone(self.decision(self.pre("Write", file_path=os.path.join(self.proj, "y.py"), content="y")))


class TestPendingTickBlocksStop(GateCase):
    def test_stop_blocks_until_ticked(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("`isa verify` passed for ISC-2 but the ISA does not tick it", err)
        self.write_isa(tick(self.text, "ISC-2"), path)
        self.pid = "p2"
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 0)


class TestCloseFreshness(GateCase):
    def test_close_needs_passes_after_last_change(self):
        self.flag("ok1")
        self.flag("ok2")
        path = self.write_isa(self.text)
        self.assertEqual(self.verify(path)[0], 0)
        self.write_isa(self.closed(), path)
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 0)
        time.sleep(0.01)
        self.post_edit_project()
        self.write_isa(self.closed(), path)
        self.pid = "p2"
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("closing needs every probe re-proven", err)
        self.assertIn("ISC-1", err)
        self.assertEqual(self.verify(path)[0], 0)
        self.pid = "p3"
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 0)


class TestAttestedWarning(GateCase):
    def test_listed_once_to_user(self):
        self.flag("ok1")
        self.flag("ok2")
        path = self.write_isa(self.text)
        self.verify(path)
        self.write_isa(self.closed(), path)
        code, out, _ = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 0)
        self.assertIn("ISC-3 (manual): checked by hand.", out.get("systemMessage", ""))
        self.assertNotIn("ISC-1", out.get("systemMessage", ""))
        self.pid = "p2"
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[1], {})


class TestPlaceholderLint(unittest.TestCase):
    def errors(self, tool, typ="bash"):
        text = FIXTURE.replace("{d}", "/x").replace("tool: test -f /x/ok2", f"tool: {tool}").replace(
            "  type: bash\n  check: flag file two", f"  type: {typ}\n  check: flag file two")
        return [m for lvl, m in lint.lint("ISA.md", "articulation", text=text).items if lvl == "ERROR"]

    def test_placeholders_in_mechanical_probe(self):
        self.assertTrue(any("placeholder (`<session-id>`)" in e for e in self.errors("isa status --session <session-id>")))
        self.assertTrue(any("placeholder (`…`)" in e for e in self.errors("grep x …")))
        self.assertEqual(self.errors("test -f /x/ok2"), [])
        self.assertEqual(self.errors("cat <<'EOF' | grep x"), [])

    def test_manual_probe_may_hold_prose(self):
        self.assertEqual(self.errors("open <the page> and look", typ="manual"), [])


class TestLedgerProtected(GateCase):
    def test_tool_writes_to_ledger_refused(self):
        self.write_isa(self.text)
        ledger = os.path.join(self.home, "_state", "evidence", "x.jsonl")
        out = self.pre("Write", file_path=ledger, content="{}")
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("written only by `isa verify`", self.reason(out))
        out = self.pre("Bash", command="echo '{}' >> ~/.isa/_state/evidence/x.jsonl")
        self.assertEqual(self.decision(out), "deny")
        self.assertIsNone(self.decision(self.pre("Bash", command="cat ~/.isa/_state/evidence/x.jsonl")))


if __name__ == "__main__":
    unittest.main()
