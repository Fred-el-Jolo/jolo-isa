"""SPEC-v2 M2: `isa new|lint|verify|close` write the engine-owned state; the hooks refuse a model edit
that would touch it. Run: python3 -m unittest tests.test_commands
"""
import json
import os
import subprocess
import sys
import unittest

from tests.test_evidence import FIXTURE, EvidenceCase, read
from tests.test_hooks import ISA, ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import classify, evidence, isafile, lint  # noqa: E402

NESTED = """---
task: "Nested fixture"
slug: 20260101-000000_t
effort: E2
phase: build
progress: 0/3
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
---

## Problem

A fixture for nested parents.

## Goal

A parent ticks with its leaves.

## Criteria

- [ ] ISC-1: both halves hold.
  - [ ] ISC-1.1: first half holds.
  - [ ] ISC-1.2: second half holds.
- [ ] ISC-2: Anti: nothing else changes.

## Test Strategy

```yaml
- isc: ISC-1.1
  type: bash
  check: flag a
  threshold: exit 0
  tool: test -f {d}/a
- isc: ISC-1.2
  type: bash
  check: flag b
  threshold: exit 0
  tool: test -f {d}/b
- isc: ISC-2
  type: bash
  check: always
  threshold: exit 0
  tool: "true"
```
"""


class CommandCase(EvidenceCase):
    def isa(self, *args, cwd=None):
        p = subprocess.run([sys.executable, ISA, *args], cwd=cwd or self.proj, env=self.env, text=True,
                           capture_output=True, timeout=60)
        return p.returncode, p.stdout + p.stderr

    def box(self, path, isc):
        return lint.parse(read(path), path)["iscs"][isc][0]

    def fm(self, path):
        return lint.parse(read(path), path)["fm"]

    def pre_isa(self, tool, **ti):
        return self.hook("PreToolUse", tool_name=tool, tool_input=ti)[1]

    def reason(self, out):
        return (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


class TestVerifyTicks(CommandCase):
    def test_round_trip(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        rc, out = self.verify(path, "ISC-2")
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.box(path, "ISC-2"))
        self.assertEqual(self.fm(path)["progress"], "1/4")
        self.assertEqual(self.fm(path)["root"], os.path.realpath(self.proj))
        lines = isafile.generated_lines(read(path))
        self.assertRegex(lines["ISC-2"], r"^- ISC-2: verified \S+ — exit 0 in [\d.]+s — `test -f .*/ok2` "
                                         r"\(ledger: 20260101-000000_t-[0-9a-f]{12}#L\d+\)$")
        n = int(lines["ISC-2"].rsplit("#L", 1)[1].rstrip(")"))
        row = json.loads(read(evidence.ledger_path(path)).splitlines()[n - 1])
        self.assertEqual((row["isc"], row["ok"], row["kind"], row["run"]), ("ISC-2", True, "verify", "green"))
        self.assertIn("re-read the ISA before editing it", out)
        self.assertEqual(lint.lint(path, "articulation").errors, 0)

    def test_all_mechanical_by_default_and_shared_probe_once(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.flag("ok2")
        rc, out = self.verify(path)
        self.assertEqual(rc, 0, out)
        for i in ("ISC-1", "ISC-2", "ISC-4"):
            self.assertTrue(self.box(path, i), i)
        self.assertFalse(self.box(path, "ISC-3"))  # self-attested: not run, not ticked
        self.assertNotIn("ISC-3", out)
        self.assertEqual(read(os.path.join(self.d, "runs")).count("run"), 1)
        rc, out = self.verify(path, "ISC-3")  # named explicitly: told how to attest it
        self.assertIn("ISC-3 SKIP", out)
        self.assertIn("--attest", out)


class TestRegressed(CommandCase):
    def test_untick_with_reason(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        self.flag("ok2", on=False)
        rc, out = self.verify(path, "ISC-2")
        self.assertEqual(rc, 1)
        self.assertFalse(self.box(path, "ISC-2"))
        self.assertRegex(isafile.generated_lines(read(path))["ISC-2"],
                         r"^- ISC-2: regressed \(passed at \S+\) — FAIL \S+ — exit 1 — `test -f .*/ok2`$")
        self.assertIn("unticked ISC-2", out)


class TestAttest(CommandCase):
    def test_self_attested_only(self):
        path = self.write_isa(self.text)
        rc, out = self.isa("verify", path, "ISC-3", "--attest", "the output reads right")
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.box(path, "ISC-3"))
        self.assertRegex(isafile.generated_lines(read(path))["ISC-3"],
                         r"^- ISC-3: attested \S+ — the output reads right \(ledger: .*#L\d+\)$")
        rc, out = self.isa("verify", path, "ISC-2", "--attest", "trust me")
        self.assertEqual(rc, 1)
        self.assertIn("has a runnable probe", out)
        self.assertFalse(self.box(path, "ISC-2"))

    def test_risk_high_refused(self):
        text = self.text.replace("  type: manual\n", "  type: manual\n  risk: high\n")
        path = self.write_isa(text)
        rc, out = self.isa("verify", path, "ISC-3", "--attest", "looked at it")
        self.assertEqual(rc, 1, out)
        self.assertIn("risk: high", out)
        self.assertFalse(self.box(path, "ISC-3"))


class TestModelTickRefused(CommandCase):
    def test_every_edit_tool(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-1")  # a pass of another ISC changes nothing for ISC-2's tick
        cur = read(path)
        ticked = cur.replace("- [ ] ISC-2:", "- [x] ISC-2:")
        for tool, ti in [("Write", dict(file_path=path, content=ticked)),
                         ("Edit", dict(file_path=path, old_string="- [ ] ISC-2:", new_string="- [x] ISC-2:")),
                         ("MultiEdit", dict(file_path=path, edits=[{"old_string": "- [ ] ISC-2:",
                                                                    "new_string": "- [x] ISC-2:"}])),
                         ("edit", dict(path=path, edits=[{"oldText": "- [ ] ISC-2:", "newText": "- [x] ISC-2:"}]))]:
            out = self.pre_isa(tool, **ti)
            self.assertEqual(self.decision(out), "deny", tool)
            self.assertIn("ticks are written by `isa verify`", self.reason(out), tool)

    def test_even_with_a_fresh_pass(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        self.write_isa(read(path).replace("- [x] ISC-2:", "- [ ] ISC-2:"), path)  # the model unticked it
        out = self.pre_isa("Edit", file_path=path, old_string="- [ ] ISC-2:", new_string="- [x] ISC-2:")
        self.assertEqual(self.decision(out), "deny")

    def test_new_isa_written_pre_ticked(self):
        other = self.isa_path("20260101-000001_other")
        out = self.pre_isa("Write", file_path=other, content=self.text.replace("- [ ] ISC-1:", "- [x] ISC-1:"))
        self.assertEqual(self.decision(out), "deny")


class TestGeneratedLineRefused(CommandCase):
    def test_add_or_change(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        line = isafile.generated_lines(read(path))["ISC-2"]
        out = self.pre_isa("Edit", file_path=path, old_string=line, new_string=line.replace("exit 0", "exit 0 (sure)"))
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("generated Verification line", self.reason(out))
        out = self.pre_isa("Edit", file_path=path, old_string=line,
                           new_string=line + "\n- ISC-1: verified 2026-01-01T00:00:00 — exit 0 in 0s — `x`")
        self.assertEqual(self.decision(out), "deny")
        out = self.pre_isa("Edit", file_path=path, old_string=line + "\n", new_string="")
        self.assertIsNone(self.decision(out))  # removing one is allowed (the engine drops orphans anyway)


class TestDeferredAllowed(CommandCase):
    def test_model_lines(self):
        path = self.write_isa(self.text + "\n## Verification\n\n- Goal: no — not done yet\n")
        for new in ["- ISC-1: [DEFERRED-VERIFY] — needs the staging box — follow-up: run it Monday\n- Goal: no — not done yet",
                    "- Goal: yes — the probes cover the goal"]:
            out = self.pre_isa("Edit", file_path=path, old_string="- Goal: no — not done yet", new_string=new)
            self.assertIsNone(self.decision(out), new)


class TestFrontmatterOwnership(CommandCase):
    def test_fields(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")  # writes root and progress 1/4
        cur = read(path)
        root = self.fm(path)["root"]
        updated = next(line for line in cur.splitlines() if line.startswith("updated:"))
        for old, new in {"phase: build": "phase: complete", "progress: 1/4": "progress: 4/4",
                         f"root: {root}": "root: /tmp"}.items():
            out = self.pre_isa("Edit", file_path=path, old_string=old, new_string=new)
            self.assertEqual(self.decision(out), "deny", new)
        for old, new in {"phase: build": "phase: verify", updated: "updated: 2026-02-02T00:00:00Z"}.items():
            out = self.pre_isa("Edit", file_path=path, old_string=old, new_string=new)
            self.assertIsNone(self.decision(out), new)
        grown = cur.replace("- [ ] ISC-4: Anti: shares the first probe.",
                            "- [ ] ISC-4: Anti: shares the first probe.\n- [ ] ISC-5: a new one.")
        out = self.pre_isa("Write", file_path=path, content=grown.replace("progress: 1/4", "progress: 1/5"))
        self.assertIsNone(self.decision(out))  # the right number is harmless


class TestUntick(CommandCase):
    def test_untick_then_orphan_dropped(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        out = self.pre_isa("Edit", file_path=path, old_string="- [x] ISC-2:", new_string="- [ ] ISC-2:")
        self.assertIsNone(self.decision(out))
        self.write_isa(read(path).replace("- [x] ISC-2:", "- [ ] ISC-2:"), path)
        rc, out = self.isa("lint", path)
        self.assertNotIn("ISC-2", isafile.generated_lines(read(path)))
        self.assertEqual(self.fm(path)["progress"], "0/4")


class TestProgressNeverBlocks(CommandCase):
    def test_add_isc(self):
        path = self.write_isa(self.text)
        grown = self.text.replace("- [ ] ISC-4: Anti: shares the first probe.",
                                  "- [ ] ISC-4: Anti: shares the first probe.\n- [ ] ISC-5: a new one.")
        grown = grown.replace("\n```\n", "\n- isc: ISC-5\n  type: bash\n  check: c\n  threshold: exit 0\n"
                                         "  tool: \"true\"\n```\n")
        self.assertIn("- isc: ISC-5", grown)
        self.write_isa(grown, path)  # progress still says 0/4: stale, and the model never touched it
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": path}, tool_response={})
        self.assertNotIn("but criteria say", self.ctx(out))  # no model-facing progress error
        self.assertIn("progress 0/5 — lint ok", self.ctx(out))  # status readers count the criteria
        self.assertIsNone(self.decision(self.edit_project()[1]))


class TestNestedParent(CommandCase):
    def test_parent_follows_leaves(self):
        path = self.write_isa(NESTED.replace("{d}", self.d))
        self.flag("a")
        self.verify(path, "ISC-1.1")
        self.assertFalse(self.box(path, "ISC-1"))
        self.flag("b")
        self.verify(path, "ISC-1.2")
        self.assertTrue(self.box(path, "ISC-1"))
        self.assertNotIn("ISC-1", isafile.generated_lines(read(path)))  # a parent gets no line
        self.flag("b", on=False)
        self.verify(path, "ISC-1.2")
        self.assertFalse(self.box(path, "ISC-1"))
        self.assertFalse(self.box(path, "ISC-1.2"))
        out = self.pre_isa("Edit", file_path=path, old_string="- [ ] ISC-1:", new_string="- [x] ISC-1:")
        self.assertEqual(self.decision(out), "deny")  # the model can't tick a parent either


LONG_PROMPT = "Add a --shout flag to greet.py that prints the greeting in uppercase, with a test"


class TestNew(CommandCase):
    def test_scaffold_and_binding(self):
        self.hook("UserPromptSubmit", prompt=LONG_PROMPT)
        rc, out = self.isa("new", "shout-flag")
        self.assertEqual(rc, 0, out)
        path = out.strip().splitlines()[-1]
        self.assertTrue(path.endswith("_shout-flag/ISA.md"))
        fm = self.fm(path)
        self.assertEqual((fm["root"], fm["stated_goal"], fm["asks"], fm["phase"], fm["effort"]),
                         (os.path.realpath(self.proj), LONG_PROMPT, [], "observe", "E3"))
        self.assertTrue(fm["slug"].endswith("_shout-flag"))
        _, hout, _ = self.hook("PostToolUse", tool_name="Bash", tool_input={"command": "isa new shout-flag"},
                               tool_response={"stdout": out, "stderr": ""})
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            st = json.load(f)
        self.assertEqual((st["bound"], st["mode"]), (os.path.realpath(path), "on"))
        self.assertIn("ISA bound", self.ctx(hout))

    def test_goal_span(self):
        self.hook("UserPromptSubmit", prompt="please " + LONG_PROMPT + " — thanks a lot")
        rc, out = self.isa("new", "t", "--goal", LONG_PROMPT, "--tier", "E2")
        self.assertEqual(rc, 0, out)
        fm = self.fm(out.strip().splitlines()[-1])
        self.assertEqual((fm["stated_goal"], fm["effort"]), (LONG_PROMPT, "E2"))

    def test_short_prompt_gives_null(self):
        self.hook("UserPromptSubmit", prompt="go")
        rc, out = self.isa("new", "t")
        self.assertEqual(rc, 0, out)
        path = out.strip().splitlines()[-1]
        self.assertIsNone(self.fm(path)["stated_goal"])
        self.assertIn("# stated_goal: copy a verbatim span", read(path))


class TestNewRefusals(CommandCase):
    def test_goal_rules(self):
        self.hook("UserPromptSubmit", prompt=LONG_PROMPT)
        rc, out = self.isa("new", "t", "--goal", "go")
        self.assertEqual(rc, 1)
        self.assertIn("minimum-content", out)
        rc, out = self.isa("new", "t", "--goal", "Remove the --shout flag from greet.py right now please")
        self.assertEqual(rc, 1)
        self.assertIn("not a verbatim span", out)
        pdir = os.path.dirname(os.path.dirname(self.isa_path()))
        self.assertEqual([f for f in (os.listdir(pdir) if os.path.isdir(pdir) else []) if f.endswith("_t")], [])

    def test_root_from_enclosing_isa(self):
        self.hook("UserPromptSubmit", prompt=LONG_PROMPT)
        rc, out = self.isa("new", "first")
        first = out.strip().splitlines()[-1]
        rc, out = self.isa("new", "second", cwd=os.path.dirname(first))
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.fm(out.strip().splitlines()[-1])["root"], os.path.realpath(self.proj))
        bare = self.isa_path("20260101-000009_bare")
        os.makedirs(os.path.dirname(bare))
        with open(bare, "w") as f:
            f.write(self.text)  # a v1 ISA: no root
        rc, out = self.isa("new", "third", cwd=os.path.dirname(bare))
        self.assertEqual(rc, 2)
        self.assertIn("no root", out)


class TestArticulationFirst(CommandCase):
    def test_no_probe_before_lint_passes(self):
        bad = self.text.replace("ISC-4: Anti:", "ISC-4:")
        path = self.write_isa(bad)
        self.flag("ok1")
        for cmd in (["verify", path], ["close", path]):
            rc, out = self.isa(*cmd)
            self.assertEqual(rc, 1, cmd)
            self.assertIn("articulation", out)
        self.assertFalse(os.path.exists(os.path.join(self.d, "runs")))  # ISC-1's probe never ran
        self.assertEqual(evidence.rows(path), [])


class TestClose(CommandCase):
    def test_close_with_summary(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.flag("ok2")
        self.verify(path)
        self.isa("verify", path, "ISC-3", "--attest", "the output reads right")
        self.write_isa(read(path).rstrip("\n") + "\n- Goal: yes — the probes cover the goal\n", path)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.fm(path)["phase"], "complete")
        self.assertIn("Proven (every probe re-run by this close):", out)
        self.assertIn("ISC-3 (manual): the output reads right", out)
        self.assertIn("- Goal: yes", out)
        self.assertEqual(lint.lint(path).errors, 0)
        closes = [r for r in evidence.rows(path) if r.get("kind") == "close"]
        self.assertEqual(sorted(r["isc"] for r in closes), ["ISC-1", "ISC-2", "ISC-4"])


class TestCloseFails(CommandCase):
    def prepared(self):
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.flag("ok2")
        self.verify(path)
        self.isa("verify", path, "ISC-3", "--attest", "fine")
        return path

    def test_failing_probe_leaves_file(self):
        path = self.prepared()
        self.write_isa(read(path).rstrip("\n") + "\n- Goal: yes — done\n", path)
        before = read(path)
        self.flag("ok2", on=False)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 1)
        self.assertIn("ISC-2: probe fails now", out)
        self.assertEqual(read(path), before)

    def test_missing_goal_line_leaves_file(self):
        path = self.prepared()
        before = read(path)
        rc, out = self.isa("close", path)
        self.assertEqual(rc, 1)
        self.assertIn("Goal: yes|no", out)
        self.assertEqual(read(path), before)


class TestIsaCommandKinds(CommandCase):
    def test_classifier(self):
        isa_md = self.isa_path()
        for cmd, want in [("isa verify x/ISA.md ISC-1", "isa-cmd"), ("cd /p && isa close a", "isa-cmd"),
                          ("isa new t --goal 'x'", "isa-cmd"), ("isa lint --close a", "isa-cmd"),
                          ("isa ls", "read"), ("isa status --session s", "read"),
                          ("isa verify a && rm -rf build", "write"),
                          (f"sed -i s/a/b/ {isa_md}", "isa-shell-edit"), (f"echo x > {isa_md}", "isa-shell-edit"),
                          (f"echo x | tee {isa_md}", "isa-shell-edit"), (f"cp /tmp/y {isa_md}", "isa-shell-edit"),
                          (f"cat {isa_md}", "read")]:
            env = os.environ.get("ISA_HOME")
            self.assertEqual(classify.bash(cmd, self.proj)[0], want, cmd)
            self.assertEqual(os.environ.get("ISA_HOME"), env)

    def test_hooks(self):
        for prompt in (None, "Fix the bug in x.py so the tests pass"):  # OFF unbound, then ON unbound
            if prompt:
                self.hook("UserPromptSubmit", prompt=prompt)
            self.assertIsNone(self.decision(self.pre_isa("Bash", command="isa verify /x/ISA.md")))
            self.assertIsNone(self.decision(self.pre_isa("Bash", command="isa new my-task")))
        path = self.write_isa(self.text)
        out = self.pre_isa("Bash", command=f"sed -i 's/- \\[ \\] ISC-1:/- [x] ISC-1:/' {path}")
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("edit an ISA.md with Write/Edit", self.reason(out))


class TestVerifyIsNotShellEdit(CommandCase):
    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)

    def test_engine_write_is_no_shell_edit(self):
        path = self.write_isa(self.text)
        self.post_edit_project()
        self.flag("ok2")
        st = os.stat(path)
        self.verify(path, "ISC-2")
        os.utime(path, (st.st_atime, st.st_mtime + 1))  # a visible mtime step on any filesystem
        _, out, _ = self.hook("PostToolUse", tool_name="Bash", tool_input={"command": f"isa verify {path} ISC-2"},
                              tool_response={"stdout": "ISC-2 PASS"})
        self.assertNotIn("ISA lint", self.ctx(out))
        _, out, _ = self.hook("PostToolUse", tool_name="Bash", tool_input={"command": "ls"}, tool_response={})
        self.assertNotIn("ISA lint", self.ctx(out))
        self.assertEqual(self.session()["since_isa"], 1)  # the project change still counts


class TestStrategySnapshot(CommandCase):
    def test_one_row(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.verify(path, "ISC-2")
        self.verify(path, "ISC-1")
        snaps = [r for r in evidence.rows(path) if r.get("kind") == "strategy"]
        self.assertEqual(len(snaps), 1)
        e = snaps[0]["entries"]
        self.assertEqual(sorted(e), ["ISC-1", "ISC-2", "ISC-3", "ISC-4"])
        self.assertEqual((e["ISC-3"]["type"], e["ISC-2"]["tool_sha"]),
                         ("manual", evidence.tool_sha(f"test -f {self.d}/ok2")))


if __name__ == "__main__":
    unittest.main()
