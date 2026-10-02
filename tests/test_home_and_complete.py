"""#1 home-dir sessions can write their ISA; #2 finished ISAs are not re-gated.
Run: python3 -m unittest tests.test_home_and_complete"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_hooks import CLOSED, E1, HookCase, ISA, ROOT

sys.path.insert(0, os.path.join(ROOT, "runtime"))
from isa import state  # noqa: E402


class TestHomeKey(unittest.TestCase):
    def setUp(self):
        # a fake $HOME outside /tmp: under /tmp the temp-dir rule would hide the bug
        self.fake = tempfile.mkdtemp(prefix="isa-fakehome-", dir=os.path.expanduser("~/.cache"))
        self.env = dict(os.environ, HOME=self.fake, ISA_SKILL_DIR=os.path.join(ROOT, "skill/ISA"))
        self.env.pop("ISA_HOME", None)

    def tearDown(self):
        shutil.rmtree(self.fake, ignore_errors=True)

    def test_home_key_is_isa_path(self):
        os.environ["ISA_HOME"] = os.path.join(self.fake, ".isa")
        try:
            self.assertTrue(state.is_isa_path(os.path.join(self.fake, ".isa", "_home", "20260101-000000_t", "ISA.md")))
        finally:
            del os.environ["ISA_HOME"]

    def test_state_dir_still_reserved(self):
        os.environ["ISA_HOME"] = os.path.join(self.fake, ".isa")
        try:
            self.assertFalse(state.is_isa_path(os.path.join(self.fake, ".isa", "_state", "sessions", "x", "ISA.md")))
        finally:
            del os.environ["ISA_HOME"]

    def test_home_session_can_write_its_isa(self):
        path = subprocess.run([sys.executable, ISA, "new", "t", "--path-only"], cwd=self.fake, env=self.env, text=True,
                              capture_output=True).stdout.strip()
        self.assertIn(os.sep + "_home" + os.sep, path)
        d = {"hook_event_name": "PreToolUse", "session_id": "home-s", "cwd": self.fake, "prompt_id": "p",
             "tool_name": "Write", "tool_input": {"file_path": path, "content": E1}}
        p = subprocess.run([sys.executable, ISA, "hook", "claude"], input=json.dumps(d), text=True,
                           capture_output=True, env=self.env)
        out = json.loads(p.stdout) if p.stdout.strip() else {}
        self.assertNotEqual((out.get("hookSpecificOutput") or {}).get("permissionDecision"), "deny", out)


class TestCompleteBinding(HookCase):
    def reason(self, out):
        return (out.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")

    def test_change_after_complete_asks_for_new_isa(self):
        self.write_isa(CLOSED)
        _, out, _ = self.edit_project()
        self.assertEqual(self.decision(out), "deny")
        self.assertIn("complete", self.reason(out))
        self.assertIn("new ISA", self.reason(out))

    def test_refusal_ignores_old_lint(self):
        broken = CLOSED.replace('tool: test "$(bun arxiv.ts 2401.12345 | wc -l)"', 'tool: test "$(bun arxiv.ts <some id> | wc -l)"')
        self.assertNotEqual(broken, CLOSED)
        self.write_isa(broken)
        _, out, _ = self.edit_project()
        self.assertEqual(self.decision(out), "deny")
        self.assertNotIn("placeholder", self.reason(out))
        self.assertNotIn("does not pass the articulation gate", self.reason(out))

    def test_quiet_turn_stop_passes(self):
        broken = CLOSED.replace('tool: test "$(bun arxiv.ts 2401.12345 | wc -l)"', 'tool: test "$(bun arxiv.ts <some id> | wc -l)"')
        self.write_isa(broken)
        self.pid = "p-quiet"
        self.config(ask_without_isa=False)
        self.hook("UserPromptSubmit", prompt="thanks, looks good")  # Jev unavailable: the model judges it
        self.hook("PreToolUse", tool_name="Read", tool_input={"file_path": "/etc/hosts"})
        code, _, err = self.hook("Stop", stop_hook_active=False,
                                 last_assistant_message="ISA judge (model): no — thanks\n\nGlad it works.")
        self.assertEqual((code, err), (0, ""))


if __name__ == "__main__":
    unittest.main()
