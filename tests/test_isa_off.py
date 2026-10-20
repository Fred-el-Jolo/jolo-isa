"""/isa-off and /isa-on (docs/2026-10-20-isa-off-01-spec.md): one class per spec section, one test per criterion of
its ISA. Same harness as test_foundations: real hooks, real `isa` commands, a fake Jev.

Run: python3 -m unittest tests.test_isa_off
"""
import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime"))
from tests.test_foundations import Case, ROOT  # noqa: E402

OFF = "ISA OFF for this session — /isa-on turns it back on"
ON = "ISA ON again — the next prompt goes through the gate"
ALREADY_OFF = "ISA is already OFF for this session"
ALREADY_ON = "ISA is already ON for this session"

SPY_JEV = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["JEV_CALLS"], "a") as f:
    f.write(sys.argv[2] + "\\n")
qs = {"isa-gate": ["work"], "isa-continuation": ["new_task", "resumes"]}.get(sys.argv[2], ["answer"])
p = float(os.environ.get("FAKE_JEV_P", "0.5"))
print(json.dumps({"ok": True, "answers": {q: {"answer": p} for q in qs}}))
"""


class Off(Case):
    def spy_jev(self, p=0.5):
        exe = self.put("spy-jev", SPY_JEV, base=self.tmp)
        os.chmod(exe, 0o755)
        self.calls = os.path.join(self.tmp, "jev-calls")
        self.env.update(ISA_JEV_BIN=exe, FAKE_JEV_P=str(p), JEV_CALLS=self.calls)

    def jev_calls(self):
        return self.read(self.calls).split() if os.path.exists(self.calls) else []

    def switch(self, text, pid):
        """The user types `/isa-off` or `/isa-on`: the hook's output."""
        rc, out, err = self.prompt(text, pid)
        self.assertEqual((rc, err), (0, ""))
        return out

    def off(self, pid="p-off"):
        return self.switch("/isa-off", pid)

    def on_again(self, pid="p-on"):
        out = self.switch("/isa-on", pid)
        self.prompt("go on", pid + "-next")  # the next prompt: the `/isa-on` prompt's pass ends with it
        return out

    def session(self, sid=None):
        try:
            with open(os.path.join(self.home, "_state", "sessions", f"claude-{sid or self.sid}.json")) as f:
                return json.load(f)
        except OSError:
            return {}

    def started(self):
        """ON through the gate (no ISA_MODE left in the environment: it would win over the switch)."""
        self.on()
        self.env.pop("ISA_MODE")

    def status(self, sid=None, json_=False):
        rc, out = self.isa("status", "--session", sid or self.sid, *(["--json"] if json_ else []))
        return json.loads(out) if json_ else out

    def guarded(self, isa):
        return [("Write", {"file_path": isa, "content": "x"}),
                ("Bash", {"command": f"echo x > {isa}"}),
                ("Bash", {"command": f"rm -rf {self.home}/_state"})]


# ------------------------------------------------------------------ S1

class S1(Off):
    def test_prompt_silent(self):
        self.spy_jev(0.5)
        _, out, _ = self.prompt("refactor the parser and its tests", "p1")
        self.assertIn("AskUserQuestion", self.context(out))
        self.assertEqual(self.jev_calls(), ["isa-gate"])
        self.off()
        os.remove(self.calls)
        for i, text in enumerate(("refactor the parser and its tests", "build the whole release pipeline")):
            rc, out, err = self.prompt(text, f"p{i + 2}")
            self.assertEqual((rc, out, err), (0, {}, ""))
        self.assertEqual(self.jev_calls(), [])

    def test_project_write_allowed(self):
        self.started()
        spec = None
        for step in ("TRIAGE", "SPEC DRAFT", "SPEC ACKED", "ISA DRAFT"):
            if step == "SPEC DRAFT":
                spec = self.spec()
            elif step == "SPEC ACKED":
                self.ack_spec(spec)
            elif step == "ISA DRAFT":
                self.isa_from(spec)
            self.assertIn(step, self.change() or "", step)
            self.off(f"off-{step}")
            self.assertIsNone(self.change(), step)
            self.on_again(f"on-{step}")

    def test_perimeter_dropped(self):
        self.started()
        isa = self.e1()
        spec = os.path.join(self.proj, "docs", "2026-10-20-x-01-spec.md")
        calls = self.guarded(isa) + [("Edit", {"file_path": spec, "old_string": "a", "new_string": "b"})]
        for tool, ti in calls:
            self.assertIsNotNone(self.deny(self.hook("PreToolUse", tool_name=tool, tool_input=ti)[1]), ti)
        self.off()
        for tool, ti in calls:
            self.assertEqual(self.hook("PreToolUse", tool_name=tool, tool_input=ti)[1], {}, ti)

    def test_stop_start_compact_silent(self):
        self.started()
        self.spec()
        self.prompt("and now?", "p2")
        self.assertEqual(self.hook("Stop")[0], 2)
        self.assertTrue(self.context(self.hook("SessionStart", source="startup")[1]))
        self.off()
        self.prompt("and now?", "p3")
        for name, kw in (("Stop", {}), ("SessionStart", {"source": "resume"}), ("PreCompact", {}),
                         ("PostCompact", {})):
            self.assertEqual(self.hook(name, **kw), (0, {}, ""), name)

    def test_state_frozen(self):
        self.started()
        spec = self.spec()
        self.ack_spec(spec)
        self.isa_from(spec)
        before = self.session()
        self.off()
        for i in range(3):
            self.prompt(f"something else {i}", f"q{i}")
        after = self.session()
        for k in ("mode", "bound", "doc", "prompts"):
            self.assertEqual(after.get(k), before.get(k), k)
        self.assertTrue(after["disabled"])

    def test_on_resumes(self):
        self.started()
        self.build()
        self.env.pop("ISA_MODE")
        self.assertIn("BUILD", self.status())
        self.off()
        self.switch("/isa-on", "p-on")
        self.assertIn("ISA ON — BUILD", self.status())
        self.spy_jev(0.1)
        _, out, _ = self.prompt("and the tests?", "p-next")
        self.assertIn("continuation", out.get("systemMessage", ""))
        self.assertEqual(self.jev_calls(), ["isa-continuation"])
        self.sid = "s2"  # nothing bound: the work question
        self.off()
        self.switch("/isa-on", "p-on")
        os.remove(self.calls)
        self.spy_jev(0.5)
        _, out, _ = self.prompt("rename the module", "p-next")
        self.assertIn("asking you", out.get("systemMessage", ""))
        self.assertEqual(self.jev_calls(), ["isa-gate"])

    def test_answer_lines(self):
        reason = lambda out: out.get("reason")  # noqa: E731
        self.assertEqual(reason(self.switch("/isa-on", "a")), ALREADY_ON)
        self.assertEqual(reason(self.off("b")), OFF)
        self.assertEqual(reason(self.off("c")), ALREADY_OFF)
        self.assertEqual(reason(self.switch("/isa-on", "d")), ON)
        self.assertEqual(reason(self.switch("/isa-on", "e")), ALREADY_ON)

    def test_isa_mode_wins(self):
        for v in ("off", "on"):
            self.env["ISA_MODE"] = v
            before = self.session()
            for text in ("/isa-off", "/isa-on"):
                out = self.switch(text, f"{v}-{text}")
                self.assertEqual(out, {"decision": "block", "reason": f"ISA_MODE={v} decides for this process"})
                self.assertNotIn("disabled", self.session())
            self.assertEqual(self.session(), before)

    def test_other_sessions(self):
        self.spy_jev(0.5)
        self.off()
        self.sid = "s2"
        _, out, _ = self.prompt("refactor the parser and its tests", "p1")
        self.assertIn("AskUserQuestion", self.context(out))
        self.assertNotIn("disabled", self.session("s2"))
        self.assertNotEqual(self.status("never-seen", json_=True)["mode"], "disabled")
        self.assertEqual(self.status("s1", json_=True)["mode"], "disabled")


# ------------------------------------------------------------------ S2

class S2(Off):
    def test_hook_blocks(self):
        d = {"hook_event_name": "UserPromptSubmit", "session_id": self.sid, "cwd": self.proj, "prompt_id": "p1",
             "transcript_path": "/dev/null", "prompt": "/isa-off"}
        rc, out, err = self.call(["hook", "claude"], json.dumps(d))
        self.assertEqual((rc, err), (0, ""))
        self.assertEqual(out.strip(), json.dumps({"decision": "block", "reason": OFF}))
        self.assertTrue(self.session()["disabled"])
        self.assertEqual(self.switch("  /isa-on \n", "p2"), {"decision": "block", "reason": ON})
        self.assertNotIn("disabled", self.session())

    def test_embedded_not_command(self):
        self.spy_jev(0.5)
        for i, text in enumerate(("please /isa-off now", "/isa-off please", "/isa-offx")):
            _, out, _ = self.prompt(text, f"p{i}")
            self.assertNotIn("decision", out, text)
            self.assertIn("AskUserQuestion", self.context(out), text)
            self.assertNotIn("disabled", self.session(), text)
        self.assertEqual(len(self.jev_calls()), 3)

    def test_off_in_any_stage(self):
        self.spy_jev(0.5)
        _, out, _ = self.prompt("rename the module", "p1")
        self.assertIn("AskUserQuestion", self.context(out))  # the gate's question is pending
        self.assertEqual(self.off()["reason"], OFF)
        self.assertEqual(self.hook("Stop"), (0, {}, ""))
        self.sid = "draft"
        self.started()
        self.spec(slug="draft")
        self.assertEqual(self.off()["reason"], OFF)
        self.sid = "build"
        self.build()
        self.env.pop("ISA_MODE")
        self.assertEqual(self.off()["reason"], OFF)
        for sid in ("s1", "draft", "build"):
            self.assertTrue(self.session(sid).get("disabled"), sid)

    def test_install_stubs(self):
        t = tempfile.mkdtemp(prefix="isa-off-install-")
        self.addCleanup(shutil.rmtree, t, True)
        settings = os.path.join(t, "claude", "settings.json")
        cmds = os.path.join(t, "claude", "commands")
        args = ["--claude-settings", settings, "--prefix", os.path.join(t, "local"), "--skills-dir",
                os.path.join(t, "skills"), "--pi-dir", os.path.join(t, "pi"), "--isa-home", os.path.join(t, "isa")]

        def install(*extra):
            p = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), *args, *extra], capture_output=True,
                               text=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout

        out = install("--dry-run")
        self.assertFalse(os.path.exists(cmds))
        for name in ("isa-off.md", "isa-on.md"):
            self.assertIn(os.path.join(cmds, name), out)
        install()
        for name in ("isa-off.md", "isa-on.md"):
            text = self.read(os.path.join(cmds, name))
            self.assertTrue(text.startswith("---\n"), name)
            self.assertIn("\ndisable-model-invocation: true\n", text.split("\n---\n")[0] + "\n")
        install("--uninstall")
        self.assertEqual(os.listdir(cmds), [])
        mine = self.put("isa-off.md", "my own command\n", base=cmds)
        out = install()
        self.assertEqual(self.read(mine), "my own command\n")
        self.assertIn(f"kept       {mine}", out)
        install("--uninstall")
        self.assertEqual(self.read(mine), "my own command\n")
        self.assertFalse(os.path.exists(os.path.join(cmds, "isa-on.md")))

    def test_no_tool_path(self):
        self.started()
        sf = os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")
        for tool, ti in (("Write", {"file_path": sf, "content": '{"disabled": true}'}),
                         ("Edit", {"file_path": sf, "old_string": "{", "new_string": '{"disabled": true, '}),
                         ("Bash", {"command": f"echo '{{\"disabled\": true}}' > {sf}"}),
                         ("Bash", {"command": f"python3 -c \"import json; json.dump({{'disabled': 1}}, open('{sf}', 'w'))\""})):
            self.assertIsNotNone(self.deny(self.hook("PreToolUse", tool_name=tool, tool_input=ti)[1]), ti)
        from isa import cli
        for cmd in ("off", "on", "disable", "enable", "switch"):
            self.assertNotIn(cmd, cli.COMMANDS)
            rc, _ = self.isa(cmd)
            self.assertEqual(rc, 2, cmd)
        self.assertNotIn("disabled", self.session())


# ------------------------------------------------------------------ S4

class S4(Off):
    def test_status_disabled(self):
        self.started()
        self.off()
        self.assertTrue(self.status().startswith("ISA DISABLED"), self.status())
        self.assertEqual(self.status(json_=True)["mode"], "disabled")

    def test_status_restored(self):
        self.started()
        self.assertTrue(self.status().startswith("ISA ON"))
        self.off()
        self.switch("/isa-on", "p-on")
        self.assertTrue(self.status().startswith("ISA ON"), self.status())
        self.sid = "s2"
        self.assertTrue(self.status().startswith("ISA OFF"))
        self.off()
        self.switch("/isa-on", "p-on")
        self.assertTrue(self.status().startswith("ISA OFF"), self.status())
        self.assertEqual(self.status(json_=True)["mode"], "off")


# ------------------------------------------------------------------ Antis

class Antis(Off):
    def test_model_cannot_flip(self):
        self.started()
        for tool, ti, resp in (("Skill", {"skill": "isa-off"}, {}),
                               ("Bash", {"command": "echo /isa-off"}, {"stdout": "/isa-off"}),
                               ("Write", {"file_path": os.path.join(self.proj, "x.md"), "content": "/isa-off"}, {}),
                               ("AskUserQuestion", {"questions": [{"question": "/isa-off?", "header": "x",
                                                                   "options": [{"label": "/isa-off"}]}],
                                                    "answers": {"/isa-off?": "/isa-off"}}, {})):
            self.hook("PreToolUse", tool_name=tool, tool_input=ti)
            self.hook("PostToolUse", tool_name=tool, tool_input=ti, tool_response=resp)
            self.assertNotIn("disabled", self.session(), tool)
        self.assertTrue(self.status().startswith("ISA ON"))


if __name__ == "__main__":
    unittest.main()
