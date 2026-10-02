"""SPEC-v2 § 11.6: the debug log — one row per ISA step in ~/.isa/_state/logs/YYYY-MM-DD.jsonl.

Run: python3 -m unittest tests.test_logs
"""
import json
import os
import shutil
import subprocess
import sys
import unittest

from tests.test_commands import CommandCase
from tests.test_hooks import ISA, HookCase


class TestHookRows(HookCase):
    def test_one_row_per_event(self):
        self.hook("SessionStart", source="startup")
        self.hook("UserPromptSubmit", prompt="hi")
        self.hook("UserPromptSubmit", prompt="Fix the bug in dates.py so the tests pass")
        self.hook("PreToolUse", tool_name="Write", tool_input={"file_path": f"{self.proj}/x.py", "content": "x"})
        self.hook("PostToolUse", tool_name="Read", tool_input={"file_path": "/etc/hosts"}, tool_response={})
        self.hook("Stop", stop_hook_active=False)
        rows = self.log_rows()
        self.assertEqual([r["step"] for r in rows],
                         ["session_start", "prompt", "prompt", "pre_tool", "post_tool", "stop"])
        for r in rows:
            self.assertEqual((r["harness"], r["session"], r["prompt_id"]), ("claude", self.sid, self.pid))
            self.assertIsInstance(r["ms"], int)
            self.assertIsInstance(r["t"], float)
            self.assertIn("decision", r)
        hi, fix = rows[1], rows[2]
        self.assertEqual((hi["prefilter"], hi["mode_before"], hi["mode_after"]), ("no", "off", "off"))
        self.assertEqual((fix["prefilter"], fix["mode_after"]), ("yes", "on"))
        self.assertEqual((rows[3]["tool"], rows[3]["decision"]), ("Write", "deny"))
        self.assertEqual(rows[5]["decision"], "block")
        self.assertNotIn("Fix the bug", json.dumps(rows))  # no prompt text in the log


class TestCmdRows(CommandCase):
    def test_commands_log_name_exit_and_ms(self):
        path = self.write_isa(self.text)
        self.flag("ok2")
        self.isa("lint", path)
        self.isa("verify", path, "ISC-2")
        self.isa("purge-logs", "--dry-run")
        self.isa("verify", path, "ISC-99")
        rows = self.log_rows("cmd")
        self.assertEqual([(r["cmd"], r["exit"]) for r in rows],
                         [("lint", 0), ("verify", 0), ("purge-logs", 0), ("verify", 2)])
        for r in rows:
            self.assertIsInstance(r["ms"], int)
        self.assertEqual(rows[1]["isa"], path)
        self.assertEqual((rows[1]["passed"], rows[1]["failed"]), (["ISC-2"], []))


class TestLogFailure(HookCase):
    def test_unwritable_log_dir_changes_nothing(self):
        prompt = "Fix the bug in dates.py so the tests pass"
        _, expected, _ = self.hook("UserPromptSubmit", prompt=prompt)
        shutil.rmtree(self.home)
        os.makedirs(os.path.join(self.home, "_state"))
        with open(os.path.join(self.home, "_state", "logs"), "w") as f:
            f.write("a file where the log folder should be\n")
        code, out, err = self.hook("UserPromptSubmit", prompt=prompt)
        self.assertEqual((code, out), (0, expected))
        self.assertNotIn("Traceback", err)
        self.assertFalse(os.path.exists(os.path.join(self.home, "_state", "errors.log")))


class TestStatusFromLog(HookCase):
    def test_gate_verdict(self):
        self.hook("UserPromptSubmit", prompt="what does cmd_list in todo.py print?")
        p = subprocess.run([sys.executable, ISA, "status", "--session", self.sid, "--json"], env=self.env,
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        gate = json.loads(p.stdout)["gate"]
        self.assertEqual((gate["verdict"], gate["source"]), ("unsure", "prefilter"))
        self.assertFalse(os.path.exists(os.path.join(self.home, "_state", "judge.jsonl")))


if __name__ == "__main__":
    unittest.main()
