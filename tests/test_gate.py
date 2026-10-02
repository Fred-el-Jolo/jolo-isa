"""SPEC-v2 M1 / § 12: the per-prompt gate and the session's ISA mode.

No test calls a real model: a fake `jev` judges — 0.93 for work prompts, 0.05 for small talk (SMALL_TALK).
Run: python3 -m unittest tests.test_gate
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_hooks import CLOSED, E1, ROOT, HookCase, setup_fake
from tests.test_shell_changes import git

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import state  # noqa: E402

SCAFFOLD = """---
task: "Review utils.py"
slug: 20260101-000000_t
effort: E2
phase: observe
progress: 0/0
started: 2026-01-01T00:00:00Z
updated: 2026-01-01T00:00:00Z
context_sufficient: false
---

## Goal

Every bug in utils.py is listed with its line number.

## Decisions

- 2026-01-01 00:00: which Python version must the fixes support?
"""


SMALL_TALK = {"hi", "thanks", "thanks!", "ok", "what does it do?"}


class GateHookCase(HookCase):
    def setUp(self):
        super().setUp()
        setup_fake(self)

    def prompt(self, text, **kw):
        self.env["FAKE_JEV_P_isa_gate"] = "0.05" if text in SMALL_TALK else "0.93"
        return self.hook("UserPromptSubmit", prompt=text, **kw)

    def msg(self, out):
        return out.get("systemMessage", "")

    def session(self):
        try:
            with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
                return json.load(f)
        except OSError:
            return {}

    def stop(self):
        return self.hook("Stop", stop_hook_active=False)


class TestOffStaysSilent(GateHookCase):
    def test_greeting(self):
        self.config(ask_without_isa=False)  # not settled as work, and nobody is asked: it goes on
        self.assertEqual(self.ctx(self.hook("SessionStart", source="startup")[1]), "")
        _, out, _ = self.prompt("hi")
        self.assertEqual(self.ctx(out), "")
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.05 → continue without ISA (asking is off)")
        self.assertEqual(self.session()["mode"], "off")
        self.hook("PreToolUse", tool_name="Read", tool_input={"file_path": "/etc/hosts"})
        self.assertEqual(self.stop()[:3:2], (0, ""))

class TestYesSwitchesOn(GateHookCase):
    def test_on_block(self):
        _, out, _ = self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.93 → ON")
        c = self.ctx(out)
        self.assertIn("[ISA: ON", c)
        self.assertIn(os.path.join(ROOT, "skill/ISA").replace(os.path.expanduser("~"), "~") + "/SKILL.md", c)
        self.assertNotIn("Read-only work", c)
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("on", "jev"))
        # ON with no ISA written yet: no judge runs (one is required already), and no second ON block
        _, out, _ = self.prompt("thanks")
        self.assertNotIn("[ISA: ON", self.ctx(out))
        self.assertEqual(self.msg(out), "")

    def test_resume_reinjects_on_block(self):
        self.prompt("Fix the bug in dates.py so the tests pass")
        self.assertIn("[ISA: ON", self.ctx(self.hook("SessionStart", source="resume")[1]))


class TestWriteWhileOff(GateHookCase):
    def test_write_switches_on_and_is_refused(self):
        self.prompt("hi")
        _, out, _ = self.edit_project()
        self.assertEqual(self.decision(out), "deny")
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("ISA: ON — this change needs an ISA first", reason)
        self.assertIn("[ISA: ON", reason)
        self.assertIn("ISA: ON", self.msg(out))
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("on", "write"))


class TestUnknownWhileOff(GateHookCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(os.path.join(self.proj, ".git"))
        git(self.proj, "init", "-q")
        with open(os.path.join(self.proj, "a.txt"), "w") as f:
            f.write("one\n")
        git(self.proj, "add", "a.txt")
        git(self.proj, "commit", "-qm", "init")

    def run_unknown(self, code, tid):
        cmd = f"python3 - <<'EOF'\n{code}\nEOF"
        pre = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tid)[1]
        subprocess.run(cmd, shell=True, cwd=self.proj, check=True, executable="/bin/bash", capture_output=True)
        post = self.hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tid,
                         tool_response={})[1]
        return pre, post

    def test_no_change_stays_off(self):
        self.config(ask_without_isa=False)
        self.prompt("hi")
        pre, _ = self.run_unknown("print(1 + 1)", "t1")
        self.assertIsNone(self.decision(pre))
        self.assertEqual(self.session()["mode"], "off")
        self.assertEqual(self.stop()[:3:2], (0, ""))

    def test_change_switches_on_and_stop_wants_an_isa(self):
        self.prompt("hi")
        pre, post = self.run_unknown("open('new.txt', 'w').write('x')", "t2")
        self.assertIsNone(self.decision(pre))
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("on", "change"))
        self.assertIn("ISA: ON", self.msg(post))
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)


class TestBindingAndSticky(GateHookCase):
    def test_binding_switches_on(self):
        self.prompt("hi")
        self.write_isa(E1)
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("on", "binding"))
        self.assertIsNone(self.decision(self.edit_project()[1]))  # no refusal on the next edit

    def test_sticky(self):
        self.prompt("Fix the bug in dates.py so the tests pass")
        for text in ("thanks", "what does it do?", "hi"):
            _, out, _ = self.prompt(text)
            self.assertNotIn("ISA: OFF", self.msg(out), text)
            self.assertEqual(self.session()["mode"], "on", text)


class TestStopNeedsIsa(GateHookCase):
    def test_review_turn_without_isa(self):
        self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.hook("PreToolUse", tool_name="Read", tool_input={"file_path": f"{self.proj}/utils.py"})
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)
        self.assertIn("context_sufficient: false", err)
        code, out, _ = self.hook("Stop", stop_hook_active=True)
        self.assertEqual(code, 0)
        self.assertIn("ending the turn anyway", self.msg(out))

    def test_isa_written_passes(self):
        self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.write_isa(E1)
        self.assertEqual(self.stop()[0], 0)


class TestScaffoldExit(GateHookCase):
    def test_creating_prompt_only(self):
        self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.write_isa(SCAFFOLD)
        self.assertEqual(self.stop()[:3:2], (0, ""))
        self.pid = "p2"
        self.prompt("ok")
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)

    def test_articulation_still_guards_changes(self):
        self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.write_isa(SCAFFOLD)
        self.assertEqual(self.decision(self.edit_project()[1]), "deny")


class TestNeedsIsaAfterComplete(GateHookCase):
    def test_second_review_after_close(self):
        self.prompt("Fix the bug in dates.py so the tests pass")
        self.write_isa(CLOSED)  # its examples' ticks have no ledger: the binding turn itself is not checked here
        self.pid = "p2"
        _, out, _ = self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.assertIn("new task: new ISA, or reopen", self.ctx(out))
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)
        self.write_isa(E1, self.isa_path("20260101-000001_review"))
        self.assertEqual(self.stop()[0], 0)

    def test_no_verdict_after_close_is_quiet(self):
        self.config(ask_without_isa=False)
        self.prompt("Fix the bug in dates.py so the tests pass")
        self.write_isa(CLOSED)
        self.pid = "p2"
        self.prompt("thanks!")
        self.assertEqual(self.stop()[:3:2], (0, ""))


class TestV1SessionFile(GateHookCase):
    def write_session(self, st):
        d = os.path.join(self.home, "_state", "sessions")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"claude-{self.sid}.json"), "w") as f:
            json.dump(st, f)

    def test_open_bound_isa_reads_on(self):
        path = self.isa_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(E1)
        self.write_session({"bound": os.path.realpath(path), "last_isa_edit": 0.0, "last_mutation": 0.0,
                            "mutations": 0, "since_isa": 0, "stop_blocks": {}, "compacted": False})
        _, out, _ = self.prompt("hi")
        self.assertNotIn("ISA: OFF", self.msg(out))
        self.assertIn("ISA bound:", self.ctx(out))

    def test_nothing_bound_reads_off(self):
        self.write_session({"bound": None, "stop_blocks": {}})
        _, out, _ = self.prompt("hi")
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.05 → asking you")
        self.assertEqual(self.session()["mode"], "off")


class TestOverride(GateHookCase):
    def test_off(self):
        self.env["ISA_MODE"] = "off"
        _, out, _ = self.prompt("Fix the bug in dates.py so the tests pass")
        self.assertEqual(out, {})
        self.assertIsNone(self.decision(self.edit_project()[1]))
        self.assertEqual(self.stop()[:3:2], (0, ""))
        self.assertEqual(self.log_rows("prompt")[-1]["mode_source"], "ISA_MODE=off")

    def test_on(self):
        self.env["ISA_MODE"] = "on"
        _, out, _ = self.prompt("hi")
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertEqual(self.session()["mode_source"], "override")


class TestPromptContext(GateHookCase):
    def rows(self):
        d = os.path.join(self.home, "_state", "prompts")
        with open(os.path.join(d, os.listdir(d)[0])) as f:
            return [json.loads(line) for line in f]

    def test_claude_transcript(self):
        tr = os.path.join(self.tmp, "transcript.jsonl")
        long_text = "x" * 3000 + " I propose to review utils.py for bugs."
        with open(tr, "w") as f:
            for m in [{"type": "user", "message": {"role": "user", "content": "hello"}},
                      {"type": "assistant", "message": {"role": "assistant", "content": [
                          {"type": "text", "text": long_text}]}},
                      {"type": "assistant", "message": {"role": "assistant", "content": [
                          {"type": "tool_use", "name": "Read", "input": {}}]}},
                      {"type": "user", "message": {"role": "user", "content": "go"}}]:
                f.write(json.dumps(m) + "\n")
        self.prompt("go", transcript_path=tr)
        row = self.rows()[-1]
        self.assertEqual(row["text"], "go")
        self.assertEqual(row["cwd"], self.proj)
        self.assertEqual(row["project"], os.path.basename(os.path.dirname(os.path.dirname(self.isa_path()))))
        self.assertTrue(row["context"].endswith("I propose to review utils.py for bugs."))
        self.assertEqual(len(row["context"]), state.CONTEXT_CHARS)

    def test_missing_transcript(self):
        self.prompt("hi", transcript_path=os.path.join(self.tmp, "nope.jsonl"))
        self.assertEqual(self.rows()[-1]["context"], "")

    def test_pi_context_field(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "runtime", "bin", "isa"), "hook", "pi"],
                           input=json.dumps({"event": "prompt", "session": "pi-s", "cwd": self.proj, "prompt_id": "x",
                                             "prompt": "go", "context": "I propose a review."}),
                           text=True, capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        d = os.path.join(self.home, "_state", "prompts")
        with open(os.path.join(d, "pi-pi-s.jsonl")) as f:
            self.assertEqual(json.loads(f.read().splitlines()[-1])["context"], "I propose a review.")


if __name__ == "__main__":
    unittest.main()
