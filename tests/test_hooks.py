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
TEST_KEY = "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktdGVzdDE="  # 32 bytes, base64


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-test-")
        self.home = os.path.join(self.tmp, "isa-home")
        self.proj = os.path.join(os.path.expanduser("~"), ".cache", "isa-test-proj-" + os.path.basename(self.tmp))
        os.makedirs(os.path.join(self.proj, ".git"))
        # no inherited ISA_* switch (e.g. from an `isa verify` run) reaches the hooks under test
        # nor the harness's "headless" markers: tests see an attended session unless they set them
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith("ISA_") and k not in ("CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_ENTRYPOINT")}
        # ISA_JEV_BIN → nothing: no test reaches the real `jev` (tests/test_jev.py points it at a fake)
        # ISA_KEY: a fixed test key, so a test project (a repo) can hold task ISAs (SPEC-v2 § 13.7)
        self.env.update(ISA_HOME=self.home, ISA_SKILL_DIR=os.path.join(ROOT, "skill/ISA"),
                        ISA_JEV_BIN=os.path.join(self.tmp, "no-jev-here"), ISA_KEY=TEST_KEY)
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

    def config(self, **settings):
        """Write ~/.isa/config.json for this test's ISA_HOME."""
        os.makedirs(self.home, exist_ok=True)
        with open(os.path.join(self.home, "config.json"), "w") as f:
            json.dump(settings, f)

    def log_rows(self, step=None):
        """Debug log rows (SPEC-v2 § 11.6) under this test's ISA_HOME, oldest first."""
        d = os.path.join(self.home, "_state", "logs")
        rows = []
        for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            with open(os.path.join(d, name)) as f:
                rows += [json.loads(line) for line in f if line.strip()]
        return [r for r in rows if step is None or r.get("step") == step]

    def isa_path(self, slug="20260101-000000_t"):
        """Where `isa new` would file a task ISA of the test project (its `.isa/` since SPEC-v2 § 13)."""
        out = subprocess.run([sys.executable, ISA, "where"], cwd=self.proj, env=self.env, text=True,
                             capture_output=True).stdout
        folder = next(line.split(":", 1)[1].strip() for line in out.splitlines() if line.startswith("ISA folder:"))
        return os.path.join(folder, slug, "ISA.md")

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
        for src in ("startup", "resume", "clear", "compact"):  # OFF / undecided: nothing is injected
            code, out, _ = self.hook("SessionStart", source=src)
            self.assertEqual((code, self.ctx(out)), (0, ""), src)
        setup_fake(self, isa_gate=0.93)
        self.hook("UserPromptSubmit", prompt="Fix the bug in x.py so the tests pass")
        for src in ("startup", "resume", "clear", "compact"):  # ON: the ON block comes back on every start
            code, out, _ = self.hook("SessionStart", source=src)
            self.assertEqual(code, 0)
            self.assertIn("[ISA: ON", self.ctx(out), src)

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


class TestReviewPromptOn(HookCase):
    """SPEC-v2: a review is work with a checkable end state — the gate turns the session ON (no more
    advice the model may ignore), reads stay free, and the turn can't end without an ISA."""
    REVIEW = "Review the whole auth module for security issues and make sure every endpoint checks the session."

    def setUp(self):
        super().setUp()
        setup_fake(self, isa_gate=0.93)  # Jev reads the review as work

    def test_review_turns_on(self):
        _, out, _ = self.hook("UserPromptSubmit", prompt=self.REVIEW)
        self.assertIn("[ISA: ON", self.ctx(out))
        self.assertNotIn("ISA fit", self.ctx(out))
        _, out, _ = self.hook("UserPromptSubmit", prompt="what time is it?")
        self.assertNotIn("[ISA: ON", self.ctx(out))  # an ON session gets no second ON block

    def test_reads_free_but_stop_needs_isa(self):
        self.hook("UserPromptSubmit", prompt=self.REVIEW)
        for tool, ti in [("Read", {"file_path": "/etc/hosts"}), ("Grep", {"pattern": "session"}),
                         ("Bash", {"command": "rg -n session src/"})]:
            _, out, _ = self.hook("PreToolUse", tool_name=tool, tool_input=ti)
            self.assertIsNone(self.decision(out), tool)
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("No ISA yet", err)


class TestGate(HookCase):
    def test_deny_unbound(self):
        code, out, _ = self.edit_project()
        self.assertEqual(code, 0)
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("this change needs an ISA first", out["hookSpecificOutput"]["permissionDecisionReason"])

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
        path = self.write_isa(E1.replace("ISC-4: Anti:", "ISC-4:"))
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": path}, tool_response={})
        self.assertIn("no `Anti:` ISC", self.ctx(out))

    def test_stale_progress_is_not_a_model_error(self):
        """SPEC-v2 § 3.1: `progress` is engine-owned — the hooks lint what `isa lint` would leave."""
        path = self.write_isa(E1.replace("progress: 0/4", "progress: 3/4"))
        _, out, _ = self.hook("PostToolUse", tool_name="Edit", tool_input={"file_path": path}, tool_response={})
        self.assertIn("progress 0/4 — lint ok", self.ctx(out))


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
        """Seamless Stop: a change after the last ISA edit is not a problem by itself …"""
        self.write_isa(E1)
        self.post_edit_project()
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[:3:2], (0, ""))
        # … a real problem (here: a lint error) blocks once, then ends with a visible warning
        self.pid = "p-lint"
        self.write_isa(E1.replace("ISC-4: Anti:", "ISC-4:"))
        self.post_edit_project()
        code, _, err = self.hook("Stop", stop_hook_active=False)
        self.assertEqual(code, 2)
        self.assertIn("no `Anti:` ISC", err)
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
        self.write_isa(E1.replace("ISC-4: Anti:", "ISC-4:"))  # a real problem: a lint error
        self.post_edit_project()
        codes = [self.hook("Stop", stop_hook_active=False)[0] for _ in range(3)]
        self.assertEqual(codes, [2, 0, 0])
        self.pid = "p2"  # a new prompt gets one new retry
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 2)


class TestShellIsaEdit(HookCase):
    """The bound ISA edited from a shell (no file-tool path names it) counts as an ISA edit."""

    def shell_edit(self, path, text, command):
        st = os.stat(path)
        with open(path, "w") as f:
            f.write(text)
        os.utime(path, (st.st_atime, st.st_mtime + 1))  # a visible mtime step on any filesystem
        return self.hook("PostToolUse", tool_name="Bash", tool_input={"command": command}, tool_response={})

    def session(self):
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            return json.load(f)

    def test_heredoc_edit_then_stop_passes(self):
        path = self.write_isa(E1)
        self.post_edit_project()
        _, out, _ = self.shell_edit(path, E1.replace("- [ ] ISC-1:", "- [x] ISC-1:").replace("0/4", "1/4"),
                                    "python3 - <<'EOF'\nopen('ISA.md','w')\nEOF")
        self.assertIn("lint ok", self.ctx(out))
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 0)

    def test_sed_on_isa_after_project_edit_clears_staleness(self):
        path = self.write_isa(E1)
        self.post_edit_project()
        self.shell_edit(path, E1.replace("- [ ] ISC-1:", "- [x] ISC-1:").replace("0/4", "1/4"),
                        f"sed -i 's/- \\[ \\] ISC-1:/- [x] ISC-1:/' {path}")
        self.assertEqual(self.hook("Stop", stop_hook_active=False)[0], 0)

    def test_shell_edit_is_linted(self):
        path = self.write_isa(E1)
        _, out, _ = self.shell_edit(path, E1.replace("ISC-4: Anti:", "ISC-4:"), "python3 - <<'EOF'\nx\nEOF")
        self.assertIn("ISA lint — ", self.ctx(out))
        self.assertIn("no `Anti:` ISC", self.ctx(out))

    def test_shell_edit_resets_stale_counter(self):
        path = self.write_isa(E1)
        for _ in range(3):
            self.post_edit_project()
        self.assertEqual(self.session()["since_isa"], 3)
        self.shell_edit(path, E1, f"sed -i s/x/y/ {path}")
        self.assertEqual(self.session()["since_isa"], 0)

    def test_untouched_isa_still_stale(self):
        """A shell command that doesn't touch the ISA is not an ISA edit (the change stays newer)."""
        self.write_isa(E1)
        self.post_edit_project()
        self.hook("PostToolUse", tool_name="Bash", tool_input={"command": "ls"}, tool_response={})
        with open(os.path.join(self.home, "_state", "sessions", f"claude-{self.sid}.json")) as f:
            st = json.load(f)
        self.assertGreater(st["last_mutation"], st["last_isa_edit"])


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




def fake_cli(dirpath, name, body):
    """An executable `name` in `dirpath` running the Python `body` (argv in sys.argv, prompt on stdin)."""
    os.makedirs(dirpath, exist_ok=True)
    path = os.path.join(dirpath, name)
    with open(path, "w") as f:
        f.write(f"#!{sys.executable}\nimport json, os, sys, time\n{body}\n")
    os.chmod(path, 0o755)
    return path


# a fake `jev` (ISA_JEV_BIN) for the gate and the advisory judgments (SPEC-v2 § 11, § 12)
FAKE_JEV = r'''
argv = sys.argv[1:]
stdin = sys.stdin.read()
with open(os.environ["FAKE_JEV_LOG"], "a") as f:
    f.write(json.dumps({"argv": argv, "presets": os.environ.get("JEV_KIT_PRESETS", ""), "stdin": stdin}) + "\n")
mode = os.environ.get("FAKE_JEV_MODE", "served")
preset = argv[1] if len(argv) > 1 else ""
def unavailable(reason, detail, code):
    print(json.dumps({"ok": False, "consumer": "isa", "unavailable": {"reason": reason, "detail": detail}}))
    sys.exit(code)
if mode == "slow":
    time.sleep(6)
if mode == "credit":
    unavailable("error", "402 Payment Required: insufficient credit balance on this account", 4)
if mode == "tripped":
    unavailable("tripped", "isa: 5 consecutive failures, cooling down 60s", 4)
if mode == "budget":
    unavailable("budget", "isa: tokensPerDay 500000 reached", 5)
if mode == "garbled":
    print("<html>bad gateway</html>")
    sys.exit(0)
d = os.environ["JEV_KIT_PRESETS"].split(":")[0]
with open(os.path.join(d, preset + ".json")) as f:
    qs = json.load(f)["questions"]
p = float(os.environ.get("FAKE_JEV_P_" + preset.replace("-", "_"), os.environ.get("FAKE_JEV_P", "0.93")))
print(json.dumps({"ok": True, "consumer": "isa", "model": "jev-1.13.0",
                  "answers": {q: {"type": "noul", "answer": float(os.environ.get("FAKE_JEV_Q_" + q, p))}
                              for q in qs}, "usage": {}}))
'''


def setup_fake(case, mode="served", **p):
    bin_ = os.path.join(case.tmp, "fakejev")
    path = fake_cli(bin_, "jev", FAKE_JEV)
    case.jev_log = os.path.join(case.tmp, "jev-calls.jsonl")
    case.env.update(ISA_JEV_BIN=path, FAKE_JEV_LOG=case.jev_log, FAKE_JEV_MODE=mode,
                    **{f"FAKE_JEV_P_{k}": str(v) for k, v in p.items()})


def calls(case, preset=None):
    try:
        with open(case.jev_log) as f:
            rows = [json.loads(line) for line in f]
    except OSError:
        return []
    return [r for r in rows if preset is None or r["argv"][1:2] == [preset]]


if __name__ == "__main__":
    unittest.main()
