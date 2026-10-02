"""SPEC-v2 M1: the per-prompt gate, the judge backends and the session's ISA mode.

No test calls a real model: the judge runs as `heuristic`, or against a fake `claude` / `pi` on PATH,
or against a fake Messages API server. Run: python3 -m unittest tests.test_gate
"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

from tests.test_hooks import CLOSED, E1, ROOT, HookCase
from tests.test_shell_changes import git

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import fit, judge  # noqa: E402

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


def fake_cli(dirpath, name, body):
    """An executable `name` in `dirpath` running the Python `body` (argv in sys.argv, prompt on stdin)."""
    os.makedirs(dirpath, exist_ok=True)
    path = os.path.join(dirpath, name)
    with open(path, "w") as f:
        f.write(f"#!{sys.executable}\nimport json, os, sys, time\n{body}\n")
    os.chmod(path, 0o755)
    return path


RECORD = """
rec = {"argv": sys.argv[1:], "stdin": sys.stdin.read(), "cwd": os.getcwd(), "files": os.listdir(os.getcwd()),
       "env": {k: os.environ.get(k) for k in ("ENABLE_CLAUDEAI_MCP_SERVERS", "ISA_JUDGE_CHILD")}}
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(rec) + "\\n")
"""
CLAUDE_YES = RECORD + """
print(json.dumps({"type": "result", "result": "", "structured_output": {"verdict": "yes", "reason": "fake yes"}}))
"""
CLAUDE_NO = RECORD + """
print(json.dumps({"type": "result", "result": '{"verdict": "no", "reason": "a question"}'}))
"""
PI_NO = RECORD + """
print(json.dumps({"type": "agent_start"}))
msg = {"role": "assistant", "content": [{"type": "text", "text": '{"verdict": "no", "reason": "pi says no"}'}]}
print(json.dumps({"type": "message_end", "message": msg}))
"""


class JudgeCase(unittest.TestCase):
    """In-process judge calls with a private PATH and log."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-judge-")
        self.bin = os.path.join(self.tmp, "bin")
        self.log = os.path.join(self.tmp, "calls.jsonl")
        self.env = mock.patch.dict(os.environ, {"PATH": self.bin + os.pathsep + "/usr/bin:/bin",
                                                "FAKE_LOG": self.log, "ISA_HOME": os.path.join(self.tmp, "h")})
        self.env.start()
        for k in ("ISA_JUDGE", "ISA_JUDGE_PI_MODEL", "ISA_JUDGE_TIMEOUT", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def calls(self):
        try:
            with open(self.log) as f:
                return [json.loads(line) for line in f]
        except OSError:
            return []


class TestPrefilter(unittest.TestCase):
    TABLE = [
        ("hi", "no"), ("thanks, looks good", "no"), ("Thank you!", "no"), ("lgtm", "no"),
        ("go", "unsure"), ("ok do it", "unsure"), ("yes", "unsure"), ("fix these", "unsure"),
        ("Fix the bug in dates.py so the tests pass", "yes"),
        ("Add a --shout flag to greet.py that prints the greeting in uppercase.", "yes"),
        ("Review utils.py for bugs and list each one with its line number.", "yes"),
        ("Write a plan for migrating the billing service to Postgres", "yes"),
        ("scaffold an ISA for the login page", "yes"),
        ("what does `is_leap` do?", "unsure"), ("explain the difference between X and Y", "unsure"),
        ("how do I fix a detached HEAD?", "unsure"), ("make the report faster", "unsure"),
    ]

    def test_table(self):
        for prompt, want in self.TABLE:
            self.assertEqual(fit.prefilter(prompt)[0], want, prompt)

    def test_reason_given(self):
        for prompt, _ in self.TABLE:
            self.assertTrue(fit.prefilter(prompt)[1], prompt)


class TestJudgeBackends(JudgeCase):
    def test_claude_isolated_call(self):
        fake_cli(self.bin, "claude", CLAUDE_YES)
        v = judge.gate("is this worth it", context="I propose to review the module.", backend="claude")
        self.assertEqual((v["verdict"], v["source"], v["reason"]), ("yes", "judge", "fake yes"))
        [c] = self.calls()
        a = c["argv"]
        self.assertEqual(a[a.index("--model") + 1], judge.DEFAULT_CLAUDE_MODEL)
        self.assertEqual(a[a.index("--tools") + 1], "")
        self.assertEqual(a[a.index("--setting-sources") + 1], "project")
        for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--json-schema"):
            self.assertIn(flag, a)
        self.assertEqual(c["env"], {"ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ISA_JUDGE_CHILD": "1"})
        self.assertEqual(c["files"], [])  # an empty temp dir
        self.assertIn("is this worth it", c["stdin"])
        self.assertIn("I propose to review the module.", c["stdin"])
        self.assertIn("checkable end state", c["stdin"])

    def test_claude_model_override_and_result_text(self):
        fake_cli(self.bin, "claude", CLAUDE_NO)
        v = judge.gate("what does it do", backend="claude:claude-sonnet-5-5")
        self.assertEqual((v["verdict"], v["reason"]), ("no", "a question"))
        a = self.calls()[0]["argv"]
        self.assertEqual(a[a.index("--model") + 1], "claude-sonnet-5-5")

    def test_pi(self):
        fake_cli(self.bin, "pi", PI_NO)
        os.environ["ISA_JUDGE_PI_MODEL"] = "anthropic/claude-haiku-4-5"
        v = judge.gate("what does it do", backend="pi")
        self.assertEqual((v["verdict"], v["reason"]), ("no", "pi says no"))
        a = self.calls()[0]["argv"]
        for flag in ("-p", "--no-session", "--no-extensions", "--no-skills", "--no-context-files", "--no-tools"):
            self.assertIn(flag, a)
        self.assertEqual(a[a.index("--model") + 1], "anthropic/claude-haiku-4-5")
        self.assertIn("what does it do", a[a.index("--") + 1])

    def test_api(self):
        seen = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.path, self.headers.get("x-api-key"), body))
                out = json.dumps({"content": [{"type": "text", "text": '{"verdict": "yes", "reason": "api yes"}'}]})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out.encode())

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            os.environ.update(ANTHROPIC_API_KEY="k-test", ANTHROPIC_BASE_URL=f"http://127.0.0.1:{srv.server_port}")
            v = judge.gate("is this a task", backend="api")
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual((v["verdict"], v["reason"]), ("yes", "api yes"))
        path, key, body = seen[0]
        self.assertEqual((path, key, body["model"]), ("/v1/messages", "k-test", judge.DEFAULT_CLAUDE_MODEL))
        self.assertNotIn("tools", body)

    def test_heuristic(self):
        self.assertEqual(judge.gate("make the report faster", backend="heuristic")["verdict"], "yes")
        self.assertEqual(judge.gate("hi", backend="heuristic")["verdict"], "no")
        self.assertEqual(self.calls(), [])

    def test_prefilter_skips_the_judge(self):
        fake_cli(self.bin, "claude", CLAUDE_NO)
        v = judge.gate("Fix the bug in dates.py so the tests pass", backend="claude")
        self.assertEqual((v["verdict"], v["source"]), ("yes", "prefilter"))
        self.assertEqual(judge.gate("thanks!", backend="claude")["source"], "prefilter")
        self.assertEqual(self.calls(), [])


class TestAutoNeverApi(JudgeCase):
    def test_auto(self):
        os.environ["ANTHROPIC_API_KEY"] = "k-test"
        os.environ["ISA_JUDGE"] = "auto"
        self.assertEqual(judge.backend_for("claude"), "heuristic")  # no claude CLI on PATH
        self.assertEqual(judge.backend_for("pi"), "heuristic")
        fake_cli(self.bin, "claude", CLAUDE_NO)
        fake_cli(self.bin, "pi", PI_NO)
        self.assertEqual(judge.backend_for("claude"), "claude")
        self.assertEqual(judge.backend_for("pi"), "pi")
        os.environ.pop("ISA_JUDGE")
        self.assertEqual(judge.backend_for("claude"), "claude")  # unset = auto
        os.environ["ISA_JUDGE"] = "api"
        self.assertEqual(judge.backend_for("claude"), "api")  # only when asked for by name


class TestJudgeFailsToOn(JudgeCase):
    def check(self, body, why):
        fake_cli(self.bin, "claude", body)
        os.environ["ISA_JUDGE_TIMEOUT"] = "1"
        v = judge.gate("what does it do", backend="claude")
        self.assertEqual((v["verdict"], v["source"]), ("yes", "error"), why)
        self.assertIn("judge unavailable", v["reason"])

    def test_timeout(self):
        self.check("time.sleep(5)", "timeout")

    def test_exit_code(self):
        self.check("sys.exit(3)", "non-zero exit")

    def test_garbage(self):
        self.check("print('certainly! the answer is maybe')", "unparseable")

    def test_missing_cli_falls_back_to_heuristic(self):
        v = judge.gate("what does it do", backend="claude")  # no claude on PATH
        self.assertEqual((v["verdict"], v["source"]), ("yes", "heuristic"))


# ------------------------------------------------------------------ engine (hooks)

class GateHookCase(HookCase):
    def prompt(self, text, **kw):
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


class TestRecursionGuard(GateHookCase):
    def test_every_event_empty(self):
        self.env["ISA_JUDGE_CHILD"] = "1"
        for name, kw in [("SessionStart", {"source": "startup"}), ("UserPromptSubmit", {"prompt": "Fix the bug"}),
                         ("PreToolUse", {"tool_name": "Write", "tool_input": {"file_path": f"{self.proj}/x.py"}}),
                         ("PostToolUse", {"tool_name": "Write", "tool_input": {"file_path": f"{self.proj}/x.py"},
                                          "tool_response": {}}),
                         ("Stop", {"stop_hook_active": False})]:
            code, out, err = self.hook(name, **kw)
            self.assertEqual((code, out, err), (0, {}, ""), name)
        self.assertFalse(os.path.exists(os.path.join(self.home, "_state", "sessions")))


class TestOffStaysSilent(GateHookCase):
    def test_greeting(self):
        self.assertEqual(self.ctx(self.hook("SessionStart", source="startup")[1]), "")
        _, out, _ = self.prompt("hi")
        self.assertEqual(self.ctx(out), "")
        self.assertTrue(self.msg(out).startswith("ISA: OFF"))
        self.assertEqual(self.session()["mode"], "off")
        self.hook("PreToolUse", tool_name="Read", tool_input={"file_path": "/etc/hosts"})
        self.assertEqual(self.stop()[:3:2], (0, ""))

    def test_judged_no(self):
        fake_cli(os.path.join(self.tmp, "bin"), "claude", CLAUDE_NO)
        self.env.update(ISA_JUDGE="claude", PATH=os.path.join(self.tmp, "bin") + os.pathsep + self.env["PATH"],
                        FAKE_LOG=os.path.join(self.tmp, "calls.jsonl"))
        _, out, _ = self.prompt("what does `is_leap` do?")
        self.assertEqual(self.ctx(out), "")
        self.assertEqual(self.msg(out), "ISA: OFF — a question")
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("off", "judge"))
        with open(os.path.join(self.home, "_state", "judge.jsonl")) as f:
            row = json.loads(f.read().splitlines()[-1])
        self.assertEqual((row["verdict"], row["source"], row["session"], row["prompt_id"]),
                         ("no", "judge", self.sid, self.pid))
        self.assertIsInstance(row["ms"], int)


class TestYesSwitchesOn(GateHookCase):
    def test_on_block(self):
        _, out, _ = self.prompt("Review utils.py for bugs and list each one with its line number.")
        self.assertTrue(self.msg(out).startswith("ISA: ON"))
        c = self.ctx(out)
        self.assertIn("[ISA: ON", c)
        self.assertIn(os.path.join(ROOT, "skill/ISA").replace(os.path.expanduser("~"), "~") + "/SKILL.md", c)
        self.assertNotIn("Read-only work", c)
        st = self.session()
        self.assertEqual((st["mode"], st["mode_source"]), ("on", "prefilter"))
        # the next prompt of an ON session is not re-judged and repeats no ON block
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
        self.assertTrue(self.msg(out).startswith("ISA: OFF"))


class TestOverride(GateHookCase):
    def test_off(self):
        self.env["ISA_MODE"] = "off"
        _, out, _ = self.prompt("Fix the bug in dates.py so the tests pass")
        self.assertEqual(out, {})
        self.assertIsNone(self.decision(self.edit_project()[1]))
        self.assertEqual(self.stop()[:3:2], (0, ""))
        with open(os.path.join(self.home, "_state", "judge.jsonl")) as f:
            self.assertEqual(json.loads(f.read().splitlines()[-1])["source"], "override")

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
        self.assertEqual(len(row["context"]), judge.CONTEXT_CHARS)

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
