"""End-to-end tests of `isa hook claude`: JSON in on stdin, exactly as Claude Code sends it.

Each test gets a throwaway ISA_HOME and project directory. Run: python3 -m unittest tests.test_hooks
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISA = os.path.join(ROOT, "runtime", "bin", "isa")
E1 = open(os.path.join(ROOT, "skill/ISA/Examples/e1-minimal.md")).read()
CLOSED = open(os.path.join(ROOT, "skill/ISA/Examples/e3-project.md")).read()


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-test-")
        self.home = os.path.join(self.tmp, "isa-home")
        self.proj = os.path.join(os.path.expanduser("~"), ".cache", "isa-test-proj-" + os.path.basename(self.tmp))
        os.makedirs(os.path.join(self.proj, ".git"))
        self.env = dict(os.environ, ISA_HOME=self.home, ISA_SKILL_DIR=os.path.join(ROOT, "skill/ISA"))
        self.sid = "s-" + os.path.basename(self.tmp)
        self.pid = "p1"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.proj, ignore_errors=True)

    # -- helpers
    def hook(self, name, **kw):
        d = {"hook_event_name": name, "session_id": self.sid, "cwd": self.proj, "prompt_id": self.pid,
             "transcript_path": "/dev/null", "permission_mode": "default"}
        d.update(kw)
        p = subprocess.run([sys.executable, ISA, "hook", "claude"], input=json.dumps(d), text=True,
                           capture_output=True, env=self.env, timeout=20)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        return p.returncode, out, p.stderr

    def isa_path(self, slug="20260101-000000_t"):
        key = subprocess.run([sys.executable, ISA, "where"], cwd=self.proj, env=self.env, text=True,
                             capture_output=True).stdout.split()[2]
        return os.path.join(self.home, key, slug, "ISA.md")

    def write_isa(self, text, path=None):
        path = path or self.isa_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": path, "content": text},
                  tool_response={})
        return path

    def edit_project(self):
        f = os.path.join(self.proj, "x.py")
        return self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": f, "content": "x"})

    def post_edit_project(self):
        f = os.path.join(self.proj, "x.py")
        return self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": f, "content": "x"},
                         tool_response={})

    def ctx(self, out):
        return (out.get("hookSpecificOutput") or {}).get("additionalContext", "")

    def decision(self, out):
        return (out.get("hookSpecificOutput") or {}).get("permissionDecision")


class TestSessionStart(HookCase):
    def test_session_start_all_sources(self):
        for src in ("startup", "resume", "clear", "compact"):
            code, out, _ = self.hook("SessionStart", source=src)
            self.assertEqual(code, 0)
            self.assertIn("[ISA protocol", self.ctx(out), src)

    def test_compact_reinjects_goal_and_open_iscs(self):
        self.write_isa(E1)
        _, out, _ = self.hook("SessionStart", source="compact")
        c = self.ctx(out)
        self.assertIn("Add a `--no-color` flag", c)
        for i in range(1, 5):
            self.assertIn(f"ISC-{i}:", c)


class TestPrompt(HookCase):
    def test_prompt_log(self):
        text = "Fix the bug in x.py — ünïcode & \"quotes\"\nsecond line"
        self.hook("UserPromptSubmit", prompt=text)
        logs = os.path.join(self.home, "_state", "prompts")
        with open(os.path.join(logs, os.listdir(logs)[0])) as f:
            line = f.read().splitlines()[-1]
        self.assertEqual(json.loads(line)["text"], text)

    def test_stated_goal_must_be_verbatim(self):
        self.hook("UserPromptSubmit", prompt="please add a no-color flag to dump.ts, thanks")
        bad = E1.replace("effort: E1\n", 'effort: E1\nstated_goal: "add a --no-color flag to dump.ts"\n')
        path = self.write_isa(bad)
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": path}, tool_response={})
        self.assertIn("stated_goal is not a verbatim substring", self.ctx(out))
        good = E1.replace("effort: E1\n", 'effort: E1\nstated_goal: "add a no-color flag to dump.ts"\n')
        self.write_isa(good, path)
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": path}, tool_response={})
        self.assertNotIn("stated_goal", self.ctx(out))
        self.assertIn("lint ok", self.ctx(out))


class TestGate(HookCase):
    def test_deny_unbound(self):
        code, out, _ = self.edit_project()
        self.assertEqual(code, 0)
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("no ISA is bound", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_deny_unbound_bash_and_mcp(self):
        _, out, _ = self.hook("PreToolUse", tool_name="Bash", tool_input={"command": "npm install left-pad"})
        self.assertEqual(self.decision(out), "deny")
        _, out, _ = self.hook("PreToolUse", tool_name="mcp__github__create_issue", tool_input={})
        self.assertEqual(self.decision(out), "deny")

    def test_reads_allowed_unbound(self):
        for tool, ti in [("Read", {"file_path": "/etc/hosts"}), ("Grep", {"pattern": "x"}),
                         ("Bash", {"command": "git status && ls -la | head"}),
                         ("Write", {"file_path": "/tmp/scratch.txt"}),
                         ("mcp__github__get_issue", {})]:
            _, out, _ = self.hook("PreToolUse", tool_name=tool, tool_input=ti)
            self.assertIsNone(self.decision(out), tool)

    def test_isa_write_allowed_unbound(self):
        _, out, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": self.isa_path()})
        self.assertIsNone(self.decision(out))

    def test_deny_articulation(self):
        no_anti = E1.replace("ISC-4: Anti:", "ISC-4:")
        self.write_isa(no_anti)
        _, out, _ = self.edit_project()
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("no `Anti:` ISC", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_bind_then_allowed(self):
        path = self.write_isa(E1)
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            st = json.load(f)
        self.assertEqual(st["bound"], os.path.realpath(path))
        _, out, _ = self.edit_project()
        self.assertIsNone(self.decision(out))

    def test_post_lint(self):
        path = self.write_isa(E1.replace("progress: 0/4", "progress: 3/4"))
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": path}, tool_response={})
        self.assertIn("progress `3/4` but criteria say 0/4", self.ctx(out))


class TestProjectInTmp(HookCase):
    """Regression: a project living under /tmp was treated as scratch and never gated (found live in pi)."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.proj, ignore_errors=True)
        self.proj = os.path.join(self.tmp, "proj-in-tmp")
        os.makedirs(os.path.join(self.proj, ".git"))

    def test_edit_in_tmp_project_is_gated(self):
        _, out, _ = self.hook("PreToolUse", tool_name="Edit", tool_input={"file_path": "greet.py"})
        self.assertEqual(self.decision(out), "deny")

    def test_scratch_outside_project_still_free(self):
        _, out, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": "/tmp/elsewhere.txt"})
        self.assertIsNone(self.decision(out))


class TestAgentMemory(HookCase):
    """ISC-27: the agent's memory folder is agent state — never gated, never counted."""

    def setUp(self):
        super().setUp()
        self.mem_root = os.path.join(self.tmp, "claude-projects")
        self.mem = os.path.join(self.mem_root, "-some-project", "memory")
        os.makedirs(self.mem)
        self.env["ISA_AGENT_MEMORY_ROOT"] = self.mem_root
        # the project itself contains the memory root, so the memory rule must win over the project rule
        self.proj = self.tmp
        os.makedirs(os.path.join(self.proj, ".git"), exist_ok=True)

    def test_memory_writes_not_gated(self):
        note = os.path.join(self.mem, "note.md")
        for tool, ti in [("Write", {"file_path": note}), ("Edit", {"file_path": os.path.join(self.mem, "MEMORY.md")}),
                         ("Bash", {"command": f"echo x >> {self.mem}/MEMORY.md"})]:
            _, out, _ = self.hook("PreToolUse", tool_name=tool, tool_input=ti)
            self.assertIsNone(self.decision(out), tool)

    def test_memory_writes_not_counted_for_stop(self):
        self.write_isa(E1)
        self.hook("PostToolUse", tool_name="Write", tool_input={"file_path": os.path.join(self.mem, "n.md")},
                  tool_response={})
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual((code, err), (0, ""))

    def test_sibling_outside_memory_still_gated(self):
        other = os.path.join(self.mem_root, "-some-project", "settings.json")
        _, out, _ = self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": other})
        self.assertEqual(self.decision(out), "deny")


class TestStop(HookCase):
    def test_stop_readonly(self):
        self.hook("PreToolUse", tool_name="Read", tool_input={"file_path": "/etc/hosts"})
        code, out, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual((code, out, err), (0, {}, ""))

    def test_stop_stale(self):
        self.write_isa(E1)
        self.post_edit_project()
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("changed after the ISA's last update", err)
        code, out, _ = self.hook("Stop", stop_hook_active=True)
        self.assertEqual(code, 0)
        self.assertIn("ending the turn anyway", out.get("systemMessage", ""))

    def test_stop_fresh_isa_passes(self):
        path = self.write_isa(E1)
        self.post_edit_project()
        self.write_isa(E1.replace("- [ ] ISC-1:", "- [x] ISC-1:").replace("0/4", "1/4"), path)
        code, out, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual((code, err), (0, ""))

    def test_stop_close(self):
        self.write_isa(CLOSED.replace("\n- Goal: yes", "\n- Note: yes"))
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("close gate", err)
        self.assertIn("Goal: yes|no", err)

    def test_stop_once(self):
        self.write_isa(E1)
        self.post_edit_project()
        codes = [self.hook("Stop", stop_hook_active=False)[0] for _ in range(3)]
        self.assertEqual(codes, [2, 0, 0])
        self.pid = "p2"  # a new prompt gets one new retry
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 2)


class TestFailOpen(HookCase):
    def test_unwritable_home(self):
        self.env["ISA_HOME"] = "/proc/definitely/not/writable"
        code, out, _ = self.post_edit_project()
        self.assertEqual(code, 0)
        self.assertIn("ISA hook error", out.get("systemMessage", ""))

    def test_crash(self):
        self.env["ISA_FAULT_INJECT"] = "1"
        code, out, err = self.edit_project()
        self.assertEqual(code, 0)
        self.assertIsNone(self.decision(out))
        self.assertIn("ISA hook error", out.get("systemMessage", ""))

    def test_garbage_input(self):
        p = subprocess.run([sys.executable, ISA, "hook", "claude"], input="not json", text=True,
                           capture_output=True, env=self.env)
        self.assertEqual(p.returncode, 0)
        self.assertIn("ISA hook error", p.stdout)


if __name__ == "__main__":
    unittest.main()
