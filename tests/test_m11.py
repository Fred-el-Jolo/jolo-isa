"""SPEC-v2 § 12, M11: Jev (else the running model) judges every prompt, and the user decides whatever
the judge does not settle as yes. Q1 "is this work?" with no ISA or a finished one; Q2 "continuation
or new task?" with an open one. Plus the binding rule, paused/superseded/resumed ledger rows, slash
commands, `isa current`, the config keys and the § 12.9 fixes. A fake `jev` plays Jev; no test reaches
the real one or a model.

Run: python3 -m unittest tests.test_m11
"""
import json
import os
import subprocess
import sys

from tests.test_commands import CommandCase
from tests.test_evidence import read
from tests.test_hooks import E1, ISA, ROOT, HookCase
from tests.test_jev import calls, setup_fake

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import evidence, lint  # noqa: E402

QUESTION = "what does cmd_list in todo.py print?"
LINE_NO = "ISA judge (model): no — a question about existing code.\n\nIt prints `1 [ ] buy milk`."
LINE_YES = "ISA judge (model): yes — this asks for a change to x.py.\n\nOn it."


class M11Case(CommandCase):
    def prompt(self, text=QUESTION, **kw):
        return self.hook("UserPromptSubmit", prompt=text, **kw)

    def msg(self, out):
        return out.get("systemMessage", "")

    def transcript(self, text):
        tr = os.path.join(self.tmp, f"tr-{len(os.listdir(self.tmp))}.jsonl")
        with open(tr, "w") as f:
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "text", "text": text}]}}) + "\n")
        return tr

    def stop(self, text="It prints the tasks."):
        return self.hook("Stop", stop_hook_active=False, transcript_path=self.transcript(text))

    def ask(self, answer, *, failed=False, question="ISA is not enabled for this prompt (Jev: 0.31). Continue?"):
        ti = {"questions": [{"question": question, "header": "ISA", "multiSelect": False, "options": [
            {"label": "Continue without ISA (Recommended)", "description": "answer without an ISA"},
            {"label": "Enable ISA", "description": "write an ISA first"}]}]}
        if failed:
            return self.hook("PostToolUseFailure", tool_name="AskUserQuestion", tool_input=ti, error="not available")
        ti["answers"] = {question: answer}
        return self.hook("PostToolUse", tool_name="AskUserQuestion", tool_input=ti, tool_response={})

    def session(self, harness="claude", sid=None):
        with open(os.path.join(self.home, "_state", "sessions", f"{harness}-{sid or self.sid}.json")) as f:
            return json.load(f)

    def isa_new(self, slug):
        """`isa new <slug>` as the model runs it: the command, then its PostToolUse (which binds)."""
        rc, out = self.isa("new", slug)
        self.assertEqual(rc, 0, out)
        path = out.strip().splitlines()[-1]
        self.hook("PostToolUse", tool_name="Bash", tool_input={"command": f"isa new {slug}"},
                  tool_response={"stdout": out})
        return path

    def open_isa(self):
        """An open ISA bound to the session (the session is then ON)."""
        return self.write_isa(self.text)

    def pi(self, event, **kw):
        d = {"event": event, "session": "pi-" + self.sid, "cwd": self.proj, "prompt_id": self.pid}
        d.update(kw)
        p = subprocess.run([sys.executable, ISA, "hook", "pi"], input=json.dumps(d), text=True,
                           capture_output=True, env=self.env, timeout=20)
        return json.loads(p.stdout or "{}")

    def q2(self, new_task, resumes=0.5):
        setup_fake(self)
        self.env.update(FAKE_JEV_Q_new_task=str(new_task), FAKE_JEV_Q_resumes=str(resumes))

    def kinds(self, path):
        return [r.get("kind") for r in evidence.rows(path)]


class TestQ1Yes(M11Case):
    def test_jev_yes_turns_on(self):
        setup_fake(self, isa_gate=0.93)
        _, out, _ = self.prompt("please check the flag files today")
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.93 → ON")
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("on", "jev"))

    def test_no_keyword_rules_left(self):
        setup_fake(self, isa_gate=0.1)
        _, out, _ = self.prompt("Fix the bug in dates.py so the tests pass")  # a work verb: Jev decides now
        self.assertNotIn("[ISA: ON", self.ctx(out))
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.10 → asking you")
        self.pid = "p2"
        self.prompt("hi")  # no greeting list either: judged like any prompt
        self.assertEqual(len(calls(self, "isa-gate")), 2)


class TestQ1Below(M11Case):
    def test_model_told_to_ask(self):
        setup_fake(self, isa_gate=0.31)
        _, out, _ = self.prompt()
        ctx = self.ctx(out)
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.31 → asking you")
        self.assertIn("AskUserQuestion", ctx)
        self.assertIn('"ISA is not enabled for this prompt (Jev: 0.31). Continue?"', ctx)
        self.assertIn('"Continue without ISA (Recommended)" and "Enable ISA"', ctx)
        self.assertNotIn("ISA judge (model)", ctx)
        self.assertEqual(self.session().get("mode", "off"), "off")

    def test_nobody_to_ask(self):
        setup_fake(self, isa_gate=0.31)
        self.env.update(CLAUDE_CODE_SESSION_ATTENDED="0", CLAUDE_CODE_ENTRYPOINT="sdk-cli")
        _, out, _ = self.prompt()
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.31 → continue without ISA (nobody to ask)")
        self.assertNotIn("AskUserQuestion", self.ctx(out))


class TestQ1Model(M11Case):
    def test_no_jev(self):
        _, out, _ = self.prompt()
        ctx = self.ctx(out)
        self.assertEqual(self.msg(out), "ISA gate — Jev unavailable (off) → the model judges")
        self.assertIn("ISA judge (model): yes|no|unsure — <one-line reason>", ctx)
        self.assertIn("AskUserQuestion", ctx)  # for a no or an unsure

    def test_credit(self):
        setup_fake(self, mode="credit")
        _, out, _ = self.prompt()
        self.assertIn("ISA gate — Jev unavailable (credit) → the model judges", self.msg(out))
        self.assertIn("Jev credit looks exhausted", self.msg(out))
        self.assertIn("ISA judge (model)", self.ctx(out))


class TestJudgeLine(M11Case):
    def test_missing_line_refused_once(self):
        self.prompt()
        code, _, err = self.stop("It prints the tasks.")
        self.assertEqual(code, 2)
        self.assertIn("ISA judge (model):", err)
        code, out, err = self.stop("It prints the tasks.")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("ending the turn anyway", self.msg(out))

    def test_line_no_then_ask(self):
        self.prompt()
        code, _, err = self.stop(LINE_NO)  # judged no, but the user was not asked
        self.assertEqual(code, 2)
        self.assertIn("the user was not asked", err)
        self.ask("Continue without ISA (Recommended)", question="ISA is not enabled for this prompt "
                 "(model: no — a question about existing code.). Continue?")
        self.assertEqual(self.stop(LINE_NO)[:3:2], (0, ""))

    def test_asked_without_line(self):
        self.prompt()
        self.ask("Continue without ISA (Recommended)")
        self.assertEqual(self.stop("It prints the tasks.")[:3:2], (0, ""))

    def test_isa_replaces_the_line(self):
        self.prompt()
        self.open_isa()
        _, _, err = self.stop("Working on it.")
        self.assertNotIn("ISA judge (model)", err)

    def test_line_alone_when_asking_is_off(self):
        self.config(ask_without_isa=False)
        self.prompt()
        self.assertEqual(self.stop(LINE_NO)[:3:2], (0, ""))


class TestJudgeLineYes(M11Case):
    def test_yes_without_isa_is_on(self):
        self.prompt()
        code, _, err = self.stop(LINE_YES)
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)
        self.assertEqual(self.session()["mode"], "on")


class TestAskChoice(M11Case):
    def test_skipped_question_refused_once(self):
        setup_fake(self, isa_gate=0.31)
        self.prompt()
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("the user was not asked", err)
        self.assertEqual(self.stop()[0], 0)

    def test_continue(self):
        setup_fake(self, isa_gate=0.31)
        self.prompt()
        self.ask("Continue without ISA (Recommended)")
        self.assertEqual(self.stop()[:3:2], (0, ""))

    def test_enable(self):
        setup_fake(self, isa_gate=0.31)
        self.prompt()
        _, out, _ = self.ask("Enable ISA")
        self.assertEqual(self.session()["mode"], "on")
        self.assertIn("[ISA: ON", self.ctx(out))
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)

    def test_nobody_to_ask(self):
        setup_fake(self, isa_gate=0.31)
        self.env.update(CLAUDE_CODE_SESSION_ATTENDED="0", CLAUDE_CODE_ENTRYPOINT="sdk-cli")
        self.prompt()
        self.assertEqual(self.stop()[:3:2], (0, ""))

    def test_question_tool_failed(self):
        setup_fake(self, isa_gate=0.31)
        self.prompt()
        self.ask(None, failed=True)
        self.assertEqual(self.stop()[:3:2], (0, ""))


class TestQ2NewTask(M11Case):
    def test_new_isa_required(self):
        old = self.open_isa()
        self.q2(new_task=0.9, resumes=0.8)
        self.pid = "p2"
        _, out, _ = self.prompt("now write the release notes for 2.0")
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.90 → new task: new ISA (open one paused)")
        self.assertEqual(len(calls(self, "isa-continuation")), 1)
        self.assertEqual(calls(self, "isa-gate"), [])
        payload = json.loads(calls(self, "isa-continuation")[0]["stdin"])
        self.assertIn("Probes decide which ISCs may be ticked.", payload["isa"])
        self.old_edit(old)  # editing the old ISA does not satisfy it
        code, _, err = self.stop()
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)
        new = self.isa_new("release-notes")
        self.assertEqual(self.session()["bound"], os.path.realpath(new))
        self.assertNotIn("No ISA yet", self.stop()[2])

    def old_edit(self, old):
        self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": old}, tool_response={})


class TestPausedSuperseded(M11Case):
    def flow(self, **q2):
        old = self.open_isa()
        if q2:
            self.q2(**q2)
        self.pid = "p2"
        self.prompt("now write the release notes for 2.0")
        new = self.isa_new("release-notes")
        return old, new

    def test_paused(self):
        old, new = self.flow(new_task=0.9, resumes=0.8)
        row = [r for r in evidence.rows(old) if r.get("kind") == "paused"]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0]["by"], os.path.basename(os.path.dirname(new)))

    def test_superseded(self):
        old, _ = self.flow(new_task=0.9, resumes=0.2)
        self.assertIn("superseded", self.kinds(old))
        self.assertNotIn("paused", self.kinds(old))

    def test_jev_unavailable_pauses(self):
        old, _ = self.flow()
        self.assertIn("paused", self.kinds(old))


class TestQ2Continuation(M11Case):
    def test_below_line(self):
        old = self.open_isa()
        self.q2(new_task=0.1)
        self.pid = "p2"
        _, out, _ = self.prompt("also handle the empty file case")
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.10 → continuation")
        self.assertNotIn("AskUserQuestion", self.ctx(out))
        self.isa_new("side-thing")
        self.assertNotIn("paused", self.kinds(old))
        self.assertNotIn("superseded", self.kinds(old))

    def test_unavailable(self):
        self.open_isa()
        self.pid = "p2"
        _, out, _ = self.prompt("also handle the empty file case")
        self.assertEqual(self.msg(out), "ISA gate — Jev unavailable → continuation (the model may start a new ISA)")
        self.assertNotIn("AskUserQuestion", self.ctx(out))
        self.assertNotIn("ISA judge (model)", self.ctx(out))


class TestBindingRule(M11Case):
    def test_edit_other_isa_keeps_binding(self):
        bound = self.open_isa()
        other = self.isa_path("20250101-000000_other")
        os.makedirs(os.path.dirname(other))
        with open(other, "w") as f:
            f.write(E1)
        self.hook("PreToolUse", tool_name="Edit", tool_input={"file_path": other, "old_string": "a", "new_string": "b"})
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": other}, tool_response={})
        self.assertEqual(self.session()["bound"], os.path.realpath(bound))
        self.assertNotIn("binding switched", self.ctx(out))

    def test_creating_an_isa_binds_it(self):
        self.open_isa()
        new = self.isa_path("20250101-000000_new")
        self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": new, "content": E1})
        os.makedirs(os.path.dirname(new))
        with open(new, "w") as f:
            f.write(E1)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": new, "content": E1}, tool_response={})
        self.assertEqual(self.session()["bound"], os.path.realpath(new))


class TestResumed(M11Case):
    def test_resume_row_and_labels(self):
        old = self.open_isa()
        self.q2(new_task=0.9, resumes=0.8)
        self.pid = "p2"
        self.prompt("now write the release notes for 2.0")
        new = self.isa_new("release-notes")
        rc, out = self.isa("ls")
        self.assertIn("paused", [line for line in out.splitlines() if "20260101-000000_t" in line][0])
        with open(new) as f:  # the new task finishes (no open ISA bound any more)
            text = f.read()
        with open(new, "w") as f:
            f.write(text.replace("phase: observe", "phase: complete"))
        self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": old}, tool_response={})
        self.assertEqual(self.session()["bound"], os.path.realpath(old))
        self.assertEqual(self.kinds(old)[-1], "resumed")
        p = subprocess.run([sys.executable, ISA, "status", "--session", self.sid, "--json"], env=self.env,
                           text=True, capture_output=True)
        self.assertIsNone(json.loads(p.stdout)["label"])

    def test_status_label(self):
        old = self.open_isa()
        evidence.record(old, [{"v": 2, "kind": "paused", "by": "x", "t": 1}])
        p = subprocess.run([sys.executable, ISA, "status", "--session", self.sid, "--json"], env=self.env,
                           text=True, capture_output=True)
        self.assertEqual(json.loads(p.stdout)["label"], "paused")


class TestSlash(M11Case):
    def skill(self, base, name, desc):
        d = os.path.join(self.proj, base, name)
        os.makedirs(d)
        with open(os.path.join(d, "SKILL.md"), "w") as f:
            f.write(f"---\nname: {name}\ndescription: \"{desc}\"\n---\n\n# {name}\n")

    def test_claude_known_and_unknown(self):
        setup_fake(self, isa_gate=0.2)
        self.skill(".claude/skills", "demo-review", "Review a file for bugs and list each one")
        self.prompt("/demo-review utils.py")
        self.assertIn("Review a file for bugs and list each one", json.loads(calls(self)[-1]["stdin"])["skill"])
        self.pid = "p2"
        self.prompt("/no-such-skill utils.py")
        self.assertEqual(json.loads(calls(self)[-1]["stdin"])["skill"], "")

    def test_pi(self):
        setup_fake(self, isa_gate=0.2)
        self.skill(".pi/skills", "demo-review", "Review a file for bugs and list each one")
        self.pi("prompt", prompt="/skill:demo-review utils.py", has_ui=True)
        self.assertIn("Review a file for bugs", json.loads(calls(self)[-1]["stdin"])["skill"])
        self.pid = "p2"
        self.pi("prompt", prompt="/skill:nope utils.py", has_ui=True)
        self.assertEqual(json.loads(calls(self)[-1]["stdin"])["skill"], "")


class TestCurrent(M11Case):
    def current(self, *args, **env):
        e = dict(self.env)
        e.pop("CLAUDE_CODE_SESSION_ID", None)
        e.pop("PI_SESSION_ID", None)
        e.update(env)
        p = subprocess.run([sys.executable, ISA, "current", *args], env=e, text=True, capture_output=True,
                           cwd=self.proj)
        return p.returncode, p.stdout + p.stderr

    def test_three_ways(self):
        path = os.path.realpath(self.open_isa())
        rc, out = self.current("--session", self.sid, "--json")
        self.assertEqual((rc, json.loads(out)["path"]), (0, path))
        self.assertEqual(json.loads(out)["tier"], "E2")
        self.assertIn("ISC-1", [i["id"] for i in json.loads(out)["open"]])
        rc, out = self.current("--json", CLAUDE_CODE_SESSION_ID=self.sid)
        self.assertEqual(json.loads(out)["path"], path)
        self.pi("post_tool", tool="write", tool_input={"path": path, "content": "x"})
        rc, out = self.current("--json", PI_SESSION_ID="pi-" + self.sid)
        self.assertEqual(json.loads(out)["path"], path)
        rc, out = self.current()
        self.assertEqual(rc, 2)
        self.assertIn("session", out)


class TestConfigKeys(M11Case):
    def test_jev_gate(self):
        setup_fake(self, isa_gate=0.9)
        self.config(jev_gate=0.95)
        _, out, _ = self.prompt()
        self.assertEqual(self.msg(out), "ISA gate — Jev 0.90 → asking you")

    def test_invalid_falls_back(self):
        setup_fake(self, isa_gate=0.9)
        for bad in ("x", 7):
            self.config(jev_gate=bad)
            _, out, _ = self.prompt()
            self.assertEqual(self.msg(out).split("\n")[0], "ISA gate — Jev 0.90 → ON")
            self.assertIn("jev_gate", self.log_rows("prompt")[-1]["config_error"])
            self.sid += "x"

    def test_jev_doubt(self):
        setup_fake(self, isa_probe=0.6)
        self.config(jev_doubt=0.7)
        path = self.write_isa(self.text)
        self.flag("ok1")
        self.flag("ok2")
        rc, out = self.verify(path)
        self.assertIn("Jev doubts ISC-2's probe would fail if the claim were false (0.6)", out)


class TestLogFields(M11Case):
    def test_jev_row(self):
        setup_fake(self, isa_gate=0.31)
        self.prompt()
        row = self.log_rows("prompt")[-1]
        self.assertEqual((row["judge"], row["question"], row["score"], row["outcome"]), ("jev", "q1", 0.31, "ask"))

    def test_model_rows(self):
        self.prompt()
        row = self.log_rows("prompt")[-1]
        self.assertEqual((row["judge"], row["question"], row["jev_reason"], row["outcome"]),
                         ("model", "q1", "off", "model"))
        self.ask("Continue without ISA (Recommended)")
        self.stop(LINE_NO)
        row = self.log_rows("stop")[-1]
        self.assertEqual((row["model_verdict"], row["choice"]), ("no", "continue"))
        self.assertEqual(row["model_reason"], "a question about existing code.")

    def test_q2_row(self):
        self.open_isa()
        self.q2(new_task=0.2)
        self.pid = "p2"
        self.prompt("also handle the empty file case")
        row = self.log_rows("prompt")[-1]
        self.assertEqual((row["judge"], row["question"], row["score"], row["outcome"]),
                         ("jev", "q2", 0.2, "continuation"))


class TestPlaceholder(M11Case):
    def lint_errors(self, tool):
        old = f"  tool: test -f {self.d}/ok2"
        self.assertIn(old, self.text)
        text = self.text.replace(old, "  tool: " + tool, 1)
        path = self.isa_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return [m for lvl, m in lint.lint(path, "articulation").items if lvl == "ERROR" and "placeholder" in m]

    def test_quoted_is_text(self):
        self.assertEqual(self.lint_errors("""grep -q "wait…" {d}/out && grep -q '<x>' {d}/out""".replace("{d}", self.d)), [])

    def test_bare_is_flagged(self):
        self.assertTrue(self.lint_errors("cat <session-id>/out"))
        self.assertTrue(self.lint_errors("test -f …/out"))


class TestLedgerPaths(M11Case):
    def pre(self, command):
        _, out, _ = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": command})
        return self.reason(out)

    def test_reads_run_writes_refused(self):
        self.open_isa()
        ev = os.path.join(self.home, "_state", "evidence")
        self.assertNotIn("evidence ledger", self.pre(f"grep -c isc {ev}/*.jsonl"))
        self.assertNotIn("evidence ledger", self.pre(f"ls {ev} && cat {ev}/a.jsonl | head"))
        self.assertIn("evidence ledger", self.pre(f"echo '{{}}' >> {ev}/a.jsonl"))
        self.assertIn("evidence ledger", self.pre(f"rm {ev}/a.jsonl"))
        self.assertIn("evidence ledger", self.pre(f"cp /tmp/x {ev}/a.jsonl"))
        _, out, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": f"{ev}/a.jsonl", "content": "x"})
        self.assertIn("evidence ledger", self.reason(out))


class TestLedgerChecksum(M11Case):
    def test_change_reported_and_close_refused(self):
        path = self.open_isa()
        self.flag("ok2")
        self.verify(path, "ISC-2")
        ledger = evidence.ledger_path(path)
        cmd = f"python3 -c \"open('{ledger}', 'a').write('{{}}' + chr(10))\""
        _, pre, _ = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id="t1")
        self.assertNotEqual(self.decision(pre), "deny")
        subprocess.run(cmd, shell=True, check=True)
        _, out, _ = self.hook("PostToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id="t1",
                              tool_response={"stdout": ""})
        self.assertIn("evidence ledger changed", self.ctx(out) + self.msg(out))
        rc, out = self.isa("close", path)
        self.assertNotEqual(rc, 0)
        self.assertIn("ledger", out)


if __name__ == "__main__":
    import unittest
    unittest.main()
