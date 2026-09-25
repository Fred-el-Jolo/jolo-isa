"""Installer against copies (never the real settings). Run: python3 -m unittest tests.test_install"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.expanduser("~/.claude/settings.json")


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="isa-inst-")
        self.settings = os.path.join(self.tmp, "settings.json")
        if os.path.isfile(REAL):
            # start from the real file minus any ISA entries a real install already added
            sys.path.insert(0, ROOT)
            import install
            with open(REAL) as f:
                base = install.strip_settings(json.load(f))
            with open(self.settings, "w") as f:
                json.dump(base, f, indent=2)
        else:
            json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "x"}]}]}},
                      open(self.settings, "w"))
        os.makedirs(os.path.join(self.tmp, "pi", "extensions"))
        self.args = ["--claude-settings", self.settings, "--prefix", os.path.join(self.tmp, "local"),
                     "--skills-dir", os.path.join(self.tmp, "skills"), "--pi-dir", os.path.join(self.tmp, "pi")]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_install(self, *extra):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), *self.args, *extra],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    @staticmethod
    def entries(s):
        return sorted((ev, json.dumps(h, sort_keys=True)) for ev, gs in s.get("hooks", {}).items()
                      for g in gs for h in g.get("hooks", []))

    def test_keeps_existing_entries(self):
        before = json.load(open(self.settings))
        self.run_install()
        after = json.load(open(self.settings))
        missing = set(self.entries(before)) - set(self.entries(after))
        self.assertEqual(missing, set())
        isa = [e for e in self.entries(after) if "isa hook claude" in e[1]]
        self.assertEqual(sorted({ev for ev, _ in isa}),
                         sorted(["PostToolUse", "PostToolUseFailure", "PreToolUse", "SessionStart", "Stop",
                                 "UserPromptSubmit"]))
        for k in before:
            if k not in ("hooks", "permissions"):
                self.assertEqual(before[k], after[k], k)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "pi", "extensions", "isa.ts")))
        self.assertTrue(os.path.islink(os.path.join(self.tmp, "local", "bin", "isa")))

    def test_idempotent(self):
        self.run_install()
        first = open(self.settings, "rb").read()
        out = self.run_install()
        self.assertEqual(open(self.settings, "rb").read(), first)
        self.assertIn("unchanged", out)
        backups = [f for f in os.listdir(self.tmp) if ".isa-backup-" in f]
        self.assertEqual(len(backups), 1)

    def test_uninstall_restores_entries(self):
        before = json.load(open(self.settings))
        self.run_install()
        self.run_install("--uninstall")
        after = json.load(open(self.settings))
        self.assertEqual(self.entries(before), self.entries(after))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "pi", "extensions", "isa.ts")))


if __name__ == "__main__":
    unittest.main()
